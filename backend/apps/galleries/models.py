from django.conf import settings
from django.db import models

from apps.core.validators import validate_image


def upload_to(instance, filename):
    import uuid, os
    return f"gallery/{instance.owner_id}/{uuid.uuid4().hex}{os.path.splitext(filename)[1].lower()}"


class GalleryImage(models.Model):
    class Source(models.TextChoices):
        UPLOAD = "upload", "Upload"
        ROOM = "room", "Room photo"
        SKETCH = "sketch", "Hand sketch"
        DRAWING = "drawing", "Drawing"
        RENDER = "render", "Render"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="gallery_images")
    project = models.ForeignKey("projects.Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="images")
    image = models.ImageField(upload_to=upload_to, validators=[validate_image])
    name = models.CharField(max_length=160)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.UPLOAD)
    favorite = models.BooleanField(default=False)
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    size_bytes = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
