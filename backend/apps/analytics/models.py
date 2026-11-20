from django.conf import settings
from django.db import models


class UsageEvent(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="usage_events")
    kind = models.CharField(max_length=40, db_index=True)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]


class SystemLog(models.Model):
    level = models.CharField(max_length=10, default="error")
    message = models.CharField(max_length=500)
    path = models.CharField(max_length=300, blank=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]


class FeatureFlag(models.Model):
    key = models.SlugField(unique=True)
    description = models.CharField(max_length=255, blank=True)
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["key"]
