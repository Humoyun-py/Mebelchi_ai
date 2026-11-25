import django_filters as filters
from rest_framework import viewsets

from apps.core.permissions import IsPlatformAdmin

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogFilter(filters.FilterSet):
    actor_email = filters.CharFilter(field_name="actor_email", lookup_expr="iexact")
    model = filters.CharFilter(field_name="model", lookup_expr="iexact")
    created_after = filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = AuditLog
        fields = ["action", "event", "model", "object_id", "actor", "actor_email"]


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Platform administrators only. Read-only: audit entries cannot be changed or deleted through the API."""

    permission_classes = [IsPlatformAdmin]
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    filterset_class = AuditLogFilter
    search_fields = ["actor_email", "object_repr", "path"]
    ordering_fields = ["created_at", "action", "model"]
