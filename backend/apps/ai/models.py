from django.conf import settings
from django.db import models


class AIUsage(models.Model):
    """One row per AI provider call (successful or not): who, which feature, which provider/model, how many tokens.
    It never stores prompts or answers, so it holds no user content; it exists for the administrators' usage and cost view."""

    class Status(models.TextChoices):
        OK = "ok", "OK"
        ERROR = "error", "Provider error"
        DISABLED = "disabled", "AI not configured"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    feature = models.CharField(max_length=40)
    provider = models.CharField(max_length=40, blank=True)
    model = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices)
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    error = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["-created_at"], name="aiusage_created_idx"),
                   models.Index(fields=["user", "-created_at"], name="aiusage_user_idx"),
                   models.Index(fields=["feature", "status"], name="aiusage_feature_idx")]

    def __str__(self):
        return f"{self.feature} {self.provider} {self.status}"
