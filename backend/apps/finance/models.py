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
        PROVIDER = "provider", "Payment provider (verified webhook)"
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


class PaymentTransaction(models.Model):
    """One transaction as the payment provider knows it (Payme, ...). The provider's own id is unique per provider, so a retried or
    duplicated call can never be counted twice. Money reaches the order only through `payment` / `refund_payment`, which are normal
    `OrderPayment` rows created by `services.settle_provider_payment` inside the same database transaction."""

    class Provider(models.TextChoices):
        PAYME = "payme", "Payme"
        CLICK = "click", "Click"
        UZUM = "uzum", "Uzum Bank"

    class Status(models.TextChoices):
        CREATED = "created", "Created, waiting for payment"
        PERFORMED = "performed", "Paid"
        CANCELLED = "cancelled", "Cancelled before payment"
        REFUNDED = "refunded", "Cancelled after payment (refunded)"

    provider = models.CharField(max_length=10, choices=Provider.choices)
    external_id = models.CharField(max_length=64, help_text="The provider's transaction id")
    order = models.ForeignKey("workshops.Order", on_delete=models.PROTECT, related_name="provider_transactions")
    amount_minor = models.BigIntegerField(help_text="Smallest currency unit (tiyin for UZS)")
    currency = models.CharField(max_length=3, default="UZS")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CREATED)
    reason = models.SmallIntegerField(null=True, blank=True, help_text="Provider's cancel reason code")
    provider_time_ms = models.BigIntegerField(null=True, blank=True, help_text="Creation time as sent by the provider (ms)")
    created_ms = models.BigIntegerField()
    performed_ms = models.BigIntegerField(null=True, blank=True)
    cancelled_ms = models.BigIntegerField(null=True, blank=True)
    payment = models.OneToOneField(OrderPayment, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    refund_payment = models.OneToOneField(OrderPayment, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["provider", "external_id"], name="paytx_provider_external_unique"),
            models.CheckConstraint(condition=Q(amount_minor__gt=0), name="paytx_amount_positive"),
            # one open invoice per order at a time, whatever the provider
            models.UniqueConstraint(fields=["order"], condition=Q(status="created"), name="paytx_one_open_per_order"),
        ]
        indexes = [models.Index(fields=["provider", "provider_time_ms"], name="paytx_provider_time_idx"),
                   models.Index(fields=["order", "-created_at"], name="paytx_order_idx")]

    def __str__(self):
        return f"{self.provider}:{self.external_id} {self.status}"
