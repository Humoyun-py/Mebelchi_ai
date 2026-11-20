from django.http import HttpResponse
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.analytics.services import track
from apps.core.views import OwnedModelViewSet

from . import assistant
from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer, SendMessageSerializer


def _reply(conv: Conversation, user_msg: Message) -> Message:
    content, meta = assistant.respond(user_msg.content, user_msg.attachments, conv.owner.language)
    conv.save()  # bump updated_at
    return Message.objects.create(conversation=conv, role=Message.Role.ASSISTANT, content=content, metadata=meta)


class ConversationViewSet(OwnedModelViewSet):
    queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer
    filterset_fields = ["project"]
    search_fields = ["title"]

    @action(detail=True, methods=["get", "post"], url_path="messages")
    def messages(self, request, pk=None):
        conv = self.get_object()
        if request.method == "GET":
            return Response(MessageSerializer(conv.messages.all(), many=True).data)
        s = SendMessageSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        attachments = s.resolve_attachments(request.user)
        first = not conv.messages.exists()
        um = Message.objects.create(conversation=conv, role=Message.Role.USER, content=s.validated_data["content"], attachments=attachments)
        if first:
            conv.title = s.validated_data["content"][:60]
        am = _reply(conv, um)
        track(request.user, "chat_message", intent=am.metadata.get("intent"))
        return Response([MessageSerializer(um).data, MessageSerializer(am).data], status=201)

    @action(detail=True, methods=["get"])
    def export(self, request, pk=None):
        conv = self.get_object()
        md = f"# {conv.title}\n\n" + "\n\n".join(f"**{'You' if m.role == 'user' else 'MEBELCHI AI'}:**\n\n{m.content}" for m in conv.messages.all())
        resp = HttpResponse(md, content_type="text/markdown; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="conversation.md"'
        return resp


class MessageViewSet(mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["patch", "delete", "post", "options"]

    def get_queryset(self):
        return Message.objects.filter(conversation__owner=self.request.user)

    def partial_update(self, request, *args, **kwargs):
        """Editing a user message replaces the assistant reply that followed it."""
        msg = self.get_object()
        if msg.role != Message.Role.USER:
            raise ValidationError({"detail": "Only your own messages can be edited."})
        content = (request.data.get("content") or "").strip()
        if not content or len(content) > 4000:
            raise ValidationError({"content": "Content is required (max 4000 characters)."})
        msg.content = content
        msg.save(update_fields=["content"])
        msg.conversation.messages.filter(id__gt=msg.id).delete()
        am = _reply(msg.conversation, msg)
        return Response([MessageSerializer(msg).data, MessageSerializer(am).data])

    @action(detail=True, methods=["post"])
    def regenerate(self, request, pk=None):
        msg = self.get_object()
        if msg.role != Message.Role.ASSISTANT:
            raise ValidationError({"detail": "Only assistant messages can be regenerated."})
        prev = msg.conversation.messages.filter(id__lt=msg.id, role=Message.Role.USER).last()
        if not prev:
            raise ValidationError({"detail": "No user message to answer."})
        msg.conversation.messages.filter(id__gte=msg.id).delete()
        return Response(MessageSerializer(_reply(msg.conversation, prev)).data, status=201)

    @action(detail=True, methods=["post"])
    def feedback(self, request, pk=None):
        msg = self.get_object()
        val = request.data.get("feedback", "")
        if val not in ("like", "dislike", ""):
            raise ValidationError({"feedback": "Use like, dislike or empty."})
        msg.feedback = "" if msg.feedback == val else val
        msg.save(update_fields=["feedback"])
        return Response(MessageSerializer(msg).data)
