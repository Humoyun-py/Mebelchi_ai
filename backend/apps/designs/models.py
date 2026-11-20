from django.conf import settings
from django.db import models


class Design(models.Model):
    class Kind(models.TextChoices):
        FURNITURE = "furniture", "Furniture"
        INTERIOR = "interior", "Interior"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="designs")
    project = models.ForeignKey("projects.Project", null=True, blank=True, on_delete=models.CASCADE, related_name="designs")
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.FURNITURE)
    name = models.CharField(max_length=160)
    config = models.JSONField(default=dict)
    room_image = models.ForeignKey("galleries.GalleryImage", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
