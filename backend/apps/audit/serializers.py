from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    action_label = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = AuditLog
        fields = ["id", "created_at", "actor", "actor_email", "action", "action_label", "event", "model", "object_id", "object_repr", "changes",
                  "ip", "method", "path"]
        read_only_fields = fields
