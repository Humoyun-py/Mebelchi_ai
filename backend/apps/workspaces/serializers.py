from rest_framework import serializers

from .models import Folder


class FolderSerializer(serializers.ModelSerializer):
    project_count = serializers.IntegerField(source="projects.count", read_only=True)

    class Meta:
        model = Folder
        fields = ["id", "name", "parent", "project_count", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_parent(self, parent):
        if parent and parent.owner_id != self.context["request"].user.id:
            raise serializers.ValidationError("Folder not found.")
        return parent
