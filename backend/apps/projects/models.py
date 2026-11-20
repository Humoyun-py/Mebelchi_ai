from django.conf import settings
from django.db import models


class Project(models.Model):
    class Category(models.TextChoices):
        CABINET = "cabinet", "Cabinet"
        KITCHEN = "kitchen", "Kitchen"
        WARDROBE = "wardrobe", "Wardrobe"
        TV_UNIT = "tv_unit", "TV unit"
        BEDROOM = "bedroom", "Bedroom"
        OFFICE = "office", "Office"
        LIVING = "living", "Living room"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="projects")
    folder = models.ForeignKey("workspaces.Folder", null=True, blank=True, on_delete=models.SET_NULL, related_name="projects")
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=16, choices=Category.choices, default=Category.CABINET)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    pinned = models.BooleanField(default=False)
    width = models.PositiveIntegerField(null=True, blank=True, help_text="mm")
    height = models.PositiveIntegerField(null=True, blank=True, help_text="mm")
    depth = models.PositiveIntegerField(null=True, blank=True, help_text="mm")
    thickness = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    material = models.ForeignKey("materials.Material", null=True, blank=True, on_delete=models.SET_NULL, related_name="projects")
    params = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-pinned", "-updated_at"]
        indexes = [models.Index(fields=["owner", "status"])]

    def __str__(self):
        return self.name


class ProjectActivity(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="activities")
    action = models.CharField(max_length=60)
    detail = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "project activities"
