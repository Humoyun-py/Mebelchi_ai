from django.conf import settings
from django.db import models


class Workshop(models.Model):
    """A furniture maker that accepts orders: either an individual master or a workshop (sex).

    One model covers both kinds, because they share the same order flow. Only approved profiles are visible
    to customers.
    """

    class Kind(models.TextChoices):
        INDIVIDUAL = "individual", "Individual master"
        WORKSHOP = "workshop", "Workshop"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        APPROVED = "approved", "Approved"
        SUSPENDED = "suspended", "Suspended"

    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workshop_profile")
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.WORKSHOP)
    name = models.CharField(max_length=160)
    city = models.CharField(max_length=80)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.status})"
