from rest_framework import serializers

from . import furniture
from .models import Design


class DesignSerializer(serializers.ModelSerializer):
    class Meta:
        model = Design
        fields = ["id", "name", "kind", "project", "config", "room_image", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def _owned(self, v, label):
        if v and v.owner_id != self.context["request"].user.id:
            raise serializers.ValidationError(f"{label} not found.")
        return v

    def validate_project(self, v):
        return self._owned(v, "Project")

    def validate_room_image(self, v):
        return self._owned(v, "Image")

    def validate(self, attrs):
        kind = attrs.get("kind") or (self.instance.kind if self.instance else Design.Kind.FURNITURE)
        if kind == Design.Kind.FURNITURE and isinstance(attrs.get("config"), dict):
            try:
                furniture.check_config(attrs["config"])
            except ValueError as e:
                raise serializers.ValidationError({"config": str(e)})
        return attrs

    def validate_config(self, v):
        if not isinstance(v, dict):
            raise serializers.ValidationError("Config must be an object.")
        import json
        if len(json.dumps(v)) > 200_000:
            raise serializers.ValidationError("Config is too large.")
        return v
