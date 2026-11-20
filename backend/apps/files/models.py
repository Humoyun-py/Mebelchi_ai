from django.conf import settings
from django.db import models

from apps.core.validators import validate_document


def upload_to(instance, filename):
    import uuid, os
    return f"files/{instance.owner_id}/{uuid.uuid4().hex}{os.path.splitext(filename)[1].lower()}"


class UserFile(models.Model):
    class Kind(models.TextChoices):
        PDF = "pdf", "PDF"
        DRAWING = "drawing", "Drawing"
        DOCUMENT = "document", "Document"
        MODEL = "model", "3D model"
        OTHER = "other", "Other"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="files")
    project = models.ForeignKey("projects.Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="files")
    file = models.FileField(upload_to=upload_to, validators=[validate_document])
    name = models.CharField(max_length=200)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.OTHER)
    size_bytes = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
