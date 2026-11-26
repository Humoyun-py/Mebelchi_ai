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

    def validate(self, attrs):
        # The database rejects a second folder with the same name under the same parent (uniq_folder_per_parent); answer 400, not 500.
        # (Root folders, parent NULL, are not covered by that constraint and stay unrestricted, as before.)
        parent = attrs.get("parent", self.instance.parent if self.instance else None)
        name = attrs.get("name", self.instance.name if self.instance else None)
        if parent is not None and name is not None:
            clash = Folder.objects.filter(owner=self.context["request"].user, parent=parent, name=name)
            if self.instance is not None:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise serializers.ValidationError({"name": "A folder with this name already exists here."})
        return attrs
