"""Money records for marketplace orders.

No payment provider is connected and no money moves through this code. A payment row records that somebody says they paid (or that an
administrator received/returned money); it counts toward the order only after a platform administrator confirms it. That is the whole
"manual payment" workflow, kept deliberately small so a real provider (Click / Payme / Uzum, webhooks, split payments) can later create
the same rows with `method="provider"` and confirm them from a verified webhook instead of by hand.
"""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

MONEY = dict(max_digits=12, decimal_places=2)


class PlatformSettings(models.Model):
    """One row (pk=1): values an administrator may change at run time."""

    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("20.00"),
                                             validators=[MinValueValidator(0), MaxValueValidator(100)])
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(commission_percent__gte=0) & Q(commission_percent__lte=100), name="platform_commission_range")]

    @classmethod
    def get(cls) -> "PlatformSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class OrderPayment(models.Model):
    class Kind(models.TextChoices):
        PAYMENT = "payment", "Payment"
        REFUND = "refund", "Refund"

    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for confirmation"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"

    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        BANK_TRANSFER = "bank_transfer", "Bank transfer"
        CARD = "card", "Card (paid outside the platform)"
        OTHER = "other", "Other"

    order = models.ForeignKey("workshops.Order", on_delete=models.PROTECT, related_name="payments")
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.PAYMENT)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    method = models.CharField(max_length=14, choices=Method.choices, default=Method.OTHER)
    amount = models.DecimalField(validators=[MinValueValidator(Decimal("0.01"))], **MONEY)
    reference = models.CharField(max_length=80, blank=True, help_text="Receipt / transfer number as written by the payer")
    note = models.CharField(max_length=255, blank=True)
    idempotency_key = models.CharField(max_length=64, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    reject_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="orderpayment_amount_positive"),
            # the same retry can never be recorded twice, and the same receipt can never be counted twice
            models.UniqueConstraint(fields=["order", "idempotency_key"], condition=Q(idempotency_key__isnull=False), name="orderpayment_idempotent"),
            models.UniqueConstraint(fields=["order", "kind", "reference"], condition=~Q(reference="") & ~Q(status="rejected"), name="orderpayment_reference_once"),
        ]
        indexes = [models.Index(fields=["status", "-created_at"], name="orderpayment_status_idx"), models.Index(fields=["order", "-created_at"], name="orderpayment_order_idx")]
