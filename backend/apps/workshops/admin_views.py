from django.db.models import Count
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import IsPlatformAdmin

from . import services
from .models import Workshop


class AdminWorkshopSerializer(serializers.ModelSerializer):
    owner_email = serializers.CharField(source="owner.email", read_only=True)
    member_count = serializers.IntegerField(read_only=True)
    order_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Workshop
        fields = ["id", "name", "kind", "city", "slug", "status", "review_note", "owner", "owner_email", "member_count", "order_count", "created_at", "updated_at"]
        read_only_fields = fields


class ReviewNoteSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)


class WorkshopAdminViewSet(viewsets.ReadOnlyModelViewSet):
    """Platform administrators review workshops: approve (pending -> active), suspend, reactivate. Every change is audited and notifies the owner.
    Administrators get no access to a workshop's orders or tasks through this endpoint."""

    permission_classes = [IsPlatformAdmin]
    serializer_class = AdminWorkshopSerializer
    queryset = Workshop.objects.none()
    filterset_fields = ["status", "kind", "city"]
    search_fields = ["name", "slug", "city", "owner__email"]
    ordering_fields = ["created_at", "name", "status"]

    def get_queryset(self):
        return (Workshop.objects.select_related("owner").annotate(member_count=Count("members", distinct=True), order_count=Count("orders", distinct=True))
                .order_by("-created_at"))

    def _review(self, request, target: str):
        note = ReviewNoteSerializer(data=request.data)
        note.is_valid(raise_exception=True)
        ws = services.review_workshop(self.get_object(), request.user, target, note.validated_data.get("note", ""))
        return Response(self.get_serializer(self.get_queryset().get(pk=ws.pk)).data)

    @extend_schema(request=ReviewNoteSerializer, responses=AdminWorkshopSerializer)
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """pending -> active (also re-activates a suspended or inactive workshop)."""
        return self._review(request, Workshop.Status.ACTIVE)

    @extend_schema(request=ReviewNoteSerializer, responses=AdminWorkshopSerializer)
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """pending -> rejected. A note explaining the decision is required; the owner is notified. The application can be approved later."""
        return self._review(request, Workshop.Status.REJECTED)

    @extend_schema(request=ReviewNoteSerializer, responses=AdminWorkshopSerializer)
    @action(detail=True, methods=["post"])
    def suspend(self, request, pk=None):
        return self._review(request, Workshop.Status.SUSPENDED)
