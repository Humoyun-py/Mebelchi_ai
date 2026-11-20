import os

from rest_framework import serializers

from apps.core.signing import sign_file

from .models import UserFile

KIND_BY_EXT = {".pdf": "pdf", ".dwg": "drawing", ".dxf": "drawing", ".glb": "model", ".gltf": "model", ".obj": "model",
               ".xlsx": "document", ".csv": "document", ".txt": "document"}


class UserFileSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = UserFile
        fields = ["id", "name", "kind", "size_bytes", "project", "file", "url", "created_at"]
        read_only_fields = ["id", "kind", "size_bytes", "url", "created_at"]
        extra_kwargs = {"file": {"write_only": True, "required": False}, "name": {"required": False}}

    def get_url(self, obj):
        return f"/api/v1/files/{obj.pk}/download/?sig={sign_file('file', obj.pk)}"

    def validate_project(self, p):
        if p and p.owner_id != self.context["request"].user.id:
            raise serializers.ValidationError("Project not found.")
        return p

    def create(self, data):
        f = data["file"]
        data.setdefault("name", f.name)
        data["size_bytes"] = f.size
        data["kind"] = KIND_BY_EXT.get(os.path.splitext(f.name)[1].lower(), "other")
        return super().create(data)
