from rest_framework import serializers

from apps.files.models import UserFile
from apps.galleries.models import GalleryImage

from .models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "role", "content", "attachments", "metadata", "feedback", "created_at"]
        read_only_fields = ["id", "role", "attachments", "metadata", "created_at"]


class ConversationSerializer(serializers.ModelSerializer):
    message_count = serializers.IntegerField(source="messages.count", read_only=True)

    class Meta:
        model = Conversation
        fields = ["id", "title", "project", "message_count", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_project(self, p):
        if p and p.owner_id != self.context["request"].user.id:
            raise serializers.ValidationError("Project not found.")
        return p


class AttachmentRef(serializers.Serializer):
    type = serializers.ChoiceField(choices=["image", "file"])
    id = serializers.IntegerField()


class SendMessageSerializer(serializers.Serializer):
    content = serializers.CharField(max_length=4000, trim_whitespace=True)
    attachments = AttachmentRef(many=True, required=False)

    def resolve_attachments(self, user):
        out = []
        for a in self.validated_data.get("attachments", []):
            model = GalleryImage if a["type"] == "image" else UserFile
            obj = model.objects.filter(pk=a["id"], owner=user).first()
            if not obj:
                raise serializers.ValidationError({"attachments": "Attachment not found."})
            out.append({"type": a["type"], "id": obj.pk, "name": obj.name})
        return out
