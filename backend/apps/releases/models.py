from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q

VERSION_RE = r"^\d{1,4}\.\d{1,4}\.\d{1,4}([-+][0-9A-Za-z.]{1,20})?$"


class AppRelease(models.Model):
    """One signed build of the mobile app that people can download from the website.

    Only `production` releases that an administrator has published are ever visible to the public. `development` builds are kept for the
    team and are never listed. The file lives in private media storage (nginx never exposes /media/) and is served by the API."""

    class Platform(models.TextChoices):
        ANDROID = "android", "Android"

    class Channel(models.TextChoices):
        PRODUCTION = "production", "Production"
        DEVELOPMENT = "development", "Development"

    platform = models.CharField(max_length=10, choices=Platform.choices, default=Platform.ANDROID)
    channel = models.CharField(max_length=12, choices=Channel.choices, default=Channel.PRODUCTION)
    version_name = models.CharField(max_length=32, validators=[RegexValidator(VERSION_RE, "Use a version like 1.2.3")])
    version_code = models.PositiveIntegerField(help_text="Android versionCode (the build number). Android refuses to install a lower number over a higher one.")
    apk = models.FileField(upload_to="releases/", max_length=200)
    sha256 = models.CharField(max_length=64, validators=[RegexValidator(r"^[0-9a-f]{64}$", "Lower-case hex SHA-256")])
    size_bytes = models.BigIntegerField()
    notes = models.TextField(blank=True, help_text="Release notes shown on the download page")
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    download_count = models.PositiveIntegerField(default=0, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version_code", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["platform", "channel", "version_code"], name="apprelease_code_unique"),
            models.CheckConstraint(condition=Q(version_code__gt=0), name="apprelease_code_positive"),
            models.CheckConstraint(condition=Q(size_bytes__gt=0), name="apprelease_size_positive"),
        ]
        indexes = [models.Index(fields=["platform", "channel", "is_published", "-version_code"], name="apprelease_public_idx")]

    def __str__(self):
        return f"{self.platform} {self.channel} {self.version_name} ({self.version_code})"
