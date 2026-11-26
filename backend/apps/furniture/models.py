from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.validators import validate_image

VIEWS = ("front", "left", "right", "back", "top", "bottom")


class FurnitureTemplate(models.Model):
    """One catalogue item. Platform templates (seeded, `workshop` empty) are always approved. A workshop or furniture maker (an individual
    workshop) adds its own items; those start as `pending` until a platform administrator approves them and only approved items are
    offered to other users and to the room designer. Sizes live in `defaults` (the cabinet engine's input), the rest is catalogue data."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    slug = models.SlugField(unique=True)
    category = models.CharField(max_length=24)
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True)
    defaults = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)          # false = removed from the catalogue (kept for history)
    workshop = models.ForeignKey("workshops.Workshop", null=True, blank=True, on_delete=models.CASCADE, related_name="catalog_items")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.APPROVED)
    review_note = models.CharField(max_length=500, blank=True, default="")
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)      # set by the workshop / admin, never guessed
    currency = models.CharField(max_length=3, default="USD")
    material = models.CharField(max_length=60, blank=True)
    color = models.CharField(max_length=7, blank=True)
    manufacturer = models.CharField(max_length=120, blank=True)
    lead_time_days = models.PositiveSmallIntegerField(null=True, blank=True)
    is_available = models.BooleanField(default=True)       # in stock / can be ordered now
    glb_file = models.FileField(upload_to="catalog/models/", blank=True)
    dedup_key = models.CharField(max_length=200, blank=True, default="", editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "name"]
        constraints = [
            models.CheckConstraint(condition=Q(price__isnull=True) | Q(price__gte=0), name="furniture_price_non_negative"),
            models.UniqueConstraint(fields=["workshop", "dedup_key"], condition=Q(workshop__isnull=False, is_active=True) & ~Q(dedup_key=""),
                                    name="furniture_no_duplicate_per_workshop"),
        ]
        indexes = [models.Index(fields=["status", "is_active"], name="furniture_status_idx"), models.Index(fields=["workshop", "status"], name="furniture_ws_status_idx")]

    def __str__(self):
        return self.name


class FurnitureImage(models.Model):
    """One picture of an item from one side. Each side exists at most once; replace it by uploading again."""

    class View(models.TextChoices):
        FRONT = "front", "Front"
        LEFT = "left", "Left"
        RIGHT = "right", "Right"
        BACK = "back", "Back"
        TOP = "top", "Top"
        BOTTOM = "bottom", "Bottom"

    template = models.ForeignKey(FurnitureTemplate, on_delete=models.CASCADE, related_name="images")
    view = models.CharField(max_length=8, choices=View.choices)
    image = models.ImageField(upload_to="catalog/images/", validators=[validate_image])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [models.UniqueConstraint(fields=["template", "view"], name="furniture_one_image_per_view")]
