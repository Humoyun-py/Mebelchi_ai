from django.conf import settings
from django.db import models


class RoomFlow(models.Model):
    """One run of the room-design conversation. The conversation state (`step`, `answers`) lives here, on the server,
    so a user can leave the web page or the Telegram chat and continue later. The 3D room and the placed furniture are
    stored in `design.config` (schema room.v1)."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        ABANDONED = "abandoned", "Abandoned"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="room_flows")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    step = models.CharField(max_length=16, default="goal")
    answers = models.JSONField(default=dict, blank=True)
    design = models.OneToOneField("designs.Design", null=True, blank=True, on_delete=models.SET_NULL, related_name="room_flow")
    photo = models.ForeignKey("galleries.GalleryImage", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["owner", "status", "-updated_at"], name="roomflow_owner_status_idx")]

    def __str__(self):
        return f"RoomFlow {self.pk} ({self.status}, {self.step})"
