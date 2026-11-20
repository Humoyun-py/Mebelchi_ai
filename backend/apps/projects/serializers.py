from rest_framework import serializers

from .models import Project, ProjectActivity


class ProjectSerializer(serializers.ModelSerializer):
    counts = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = ["id", "name", "description", "category", "status", "pinned", "folder", "width", "height", "depth", "thickness",
                  "material", "params", "counts", "created_at", "updated_at"]
        read_only_fields = ["id", "status", "counts", "created_at", "updated_at"]

    def get_counts(self, obj):
        return {"calculations": obj.calculations.count(), "cutting_lists": obj.cutting_lists.count(), "designs": obj.designs.count(),
                "images": obj.images.count(), "files": obj.files.count()}

    def _own(self, obj, label):
        if obj and getattr(obj, "owner_id", self.context["request"].user.id) != self.context["request"].user.id:
            raise serializers.ValidationError(f"{label} not found.")
        return obj

    def validate_folder(self, v):
        return self._own(v, "Folder")

    def validate_material(self, v):
        if v and not v.is_system and v.owner_id != self.context["request"].user.id:
            raise serializers.ValidationError("Material not found.")
        return v

    def validate(self, a):
        for k, lo, hi in (("width", 100, 6000), ("height", 100, 4000), ("depth", 50, 2000)):
            if a.get(k) is not None and not lo <= a[k] <= hi:
                raise serializers.ValidationError({k: f"Must be between {lo} and {hi} mm."})
        return a


class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectActivity
        fields = ["id", "action", "detail", "created_at"]
