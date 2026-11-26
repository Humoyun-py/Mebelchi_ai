from PIL import Image
from rest_framework import serializers

from apps.core.signing import sign_file

from .models import GalleryImage


class GalleryImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = GalleryImage
        fields = ["id", "name", "source", "favorite", "project", "image", "url", "width", "height", "size_bytes", "created_at"]
        read_only_fields = ["id", "url", "width", "height", "size_bytes", "created_at"]
        extra_kwargs = {"image": {"write_only": True, "required": False}, "name": {"required": False}}

    def get_url(self, obj):
        return f"/api/v1/gallery/{obj.pk}/file/?sig={sign_file('image', obj.pk)}"

    def validate(self, attrs):
        if self.instance is None and "image" not in attrs:
            raise serializers.ValidationError({"image": "No image was submitted."})
        return attrs

    def validate_project(self, p):
        if p and p.owner_id != self.context["request"].user.id:
            raise serializers.ValidationError("Project not found.")
        return p

    def create(self, data):
        f = data["image"]
        img = Image.open(f)
        data["width"], data["height"] = img.size
        f.seek(0)
        data["size_bytes"] = f.size
        data.setdefault("name", f.name.rsplit(".", 1)[0][:160])
        return super().create(data)
