from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.audit import services as audit
from apps.core.permissions import IsPlatformAdmin

from .models import Workshop
from .serializers import WorkshopSerializer


class WorkshopAdminViewSet(viewsets.ReadOnlyModelViewSet):
    """Administrators review workshop profiles. Every status change is written to the audit log."""

    permission_classes = [IsPlatformAdmin]
    serializer_class = WorkshopSerializer
    queryset = Workshop.objects.select_related("owner").order_by("-created_at")
    filterset_fields = ["status", "kind", "city"]
    search_fields = ["name", "owner__email"]

    def _change_status(self, request, target: str, allowed_from: set[str]):
        profile = self.get_object()
        if profile.status not in allowed_from:
            raise ValidationError({"status": f"Cannot change status from '{profile.status}' to '{target}'."})
        with transaction.atomic():
            previous = profile.status
            profile.status = target
            profile.save(update_fields=["status", "updated_at"])
            audit.record(f"workshop.{target}", actor=request.user, target_type="workshop", target_id=profile.pk,
                         changes={"status": [previous, target]})
        return Response(WorkshopSerializer(profile).data, status=status.HTTP_200_OK)

    @extend_schema(request=None, responses=WorkshopSerializer)
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._change_status(request, Workshop.Status.APPROVED, {Workshop.Status.PENDING, Workshop.Status.SUSPENDED})

    @extend_schema(request=None, responses=WorkshopSerializer)
    @action(detail=True, methods=["post"])
    def suspend(self, request, pk=None):
        return self._change_status(request, Workshop.Status.SUSPENDED, {Workshop.Status.APPROVED})
