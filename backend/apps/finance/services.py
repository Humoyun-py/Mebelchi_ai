"""Commission arithmetic and the manual payment workflow. Every amount is a Decimal rounded half-up to 2 places; nothing here uses floats."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.services import record, save_with_event
from apps.notifications.services import notify
from apps.workshops.models import Order

from .models import OrderPayment, PlatformSettings

CENT = Decimal("0.01")
P, Status = OrderPayment, OrderPayment.Status


def money(v) -> Decimal:
    return Decimal(str(v)).quantize(CENT, rounding=ROUND_HALF_UP)


def commission_percent() -> Decimal:
    return PlatformSettings.get().commission_percent


def split(total, percent=None) -> tuple[Decimal, Decimal]:
    """(platform commission, workshop amount). The two always add up to the total to the cent."""
    pct = commission_percent() if percent is None else Decimal(str(percent))
    total = money(total)
    commission = money(total * pct / 100)
    return commission, total - commission


def err(field, msg):
    return ValidationError({field: msg})


def set_commission_percent(actor, value) -> PlatformSettings:
    try:
        v = Decimal(str(value))
    except Exception:  # noqa: BLE001
        raise err("commission_percent", "must be a number")
    if not Decimal("0") <= v <= Decimal("100") or v != v.quantize(CENT):
        raise err("commission_percent", "must be between 0 and 100 with at most 2 decimals")
    with transaction.atomic():
        s = PlatformSettings.get()
        old = s.commission_percent
        s.commission_percent, s.updated_by = v, actor
        s.save()
        record("update", model="finance.PlatformSettings", object_id=1, object_repr="commission", changes={"commission_percent": [str(old), str(v)]},
               actor=actor, event="finance.commission_changed")
    return s


def _validate_amount(order: Order, kind: str, amount: Decimal):
    if amount <= 0:
        raise err("amount", "must be greater than zero")
    if order.source != Order.Source.MARKETPLACE:
        raise err("order", "Only marketplace orders have platform payments.")
    if order.status in (Order.Status.PENDING, Order.Status.REJECTED, Order.Status.CANCELLED) and kind == P.Kind.PAYMENT:
        raise err("order", f"A {order.status} order cannot be paid.")
    if order.payment_status == Order.PaymentStatus.REFUNDED:
        raise err("order", "This order was fully refunded; its payment record is closed.")
    if kind == P.Kind.PAYMENT and order.paid_amount + amount > order.total_price:
        raise err("amount", f"This would pay more than the order total ({order.total_price}); at most {order.total_price - order.paid_amount} is still due.")
    if kind == P.Kind.REFUND and amount > order.paid_amount:
        raise err("amount", f"Only {order.paid_amount} has been paid, so at most that can be refunded.")


def create_payment(actor, order: Order, *, kind: str, amount, method: str, reference: str = "", note: str = "", idempotency_key: str | None = None) -> tuple[OrderPayment, bool]:
    """Records a payment / refund as PENDING. Returns (row, created); a repeated idempotency key returns the first row."""
    amount = money(amount)
    if method not in P.Method.values:
        raise err("method", f"must be one of: {', '.join(P.Method.values)}")
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if idempotency_key:
            same = P.objects.filter(order=order, idempotency_key=idempotency_key).first()
            if same:
                return same, False
        _validate_amount(order, kind, amount)
        try:
            with transaction.atomic():
                row = P.objects.create(order=order, kind=kind, amount=amount, method=method, reference=reference.strip()[:80], note=note[:255],
                                       idempotency_key=idempotency_key or None, created_by=actor)
        except IntegrityError:
            raise err("reference", "This receipt number is already recorded for the order.")
        record("create", model="finance.OrderPayment", object_id=row.pk, object_repr=f"{kind} {amount} {order.order_number}", actor=actor,
               event=f"payment.{kind}_recorded")
        return row, True


def confirm_payment(actor, payment_id: int) -> OrderPayment:
    if not (actor.is_staff or actor.is_superuser):
        raise PermissionDenied("Only a platform administrator can confirm payments.")
    with transaction.atomic():
        row = P.objects.select_for_update(of=("self",)).select_related("order").get(pk=payment_id)
        if row.status != Status.PENDING:
            raise err("status", f"This payment is already {row.status}.")
        order = Order.objects.select_for_update(of=("self",)).select_related("customer_user", "workshop__owner").get(pk=row.order_id)
        _validate_amount(order, row.kind, row.amount)
        if row.kind == P.Kind.PAYMENT:
            order.paid_amount += row.amount
            order.payment_status = Order.PaymentStatus.PAID if order.paid_amount >= order.total_price else Order.PaymentStatus.PARTIALLY_PAID
        else:
            if row.amount == order.paid_amount:
                order.payment_status = Order.PaymentStatus.REFUNDED         # full refund: paid_amount stays as history, the record is closed
            else:
                order.paid_amount -= row.amount
                order.payment_status = Order.PaymentStatus.PAID if order.paid_amount >= order.total_price else (
                    Order.PaymentStatus.PARTIALLY_PAID if order.paid_amount > 0 else Order.PaymentStatus.UNPAID)
        save_with_event(order, f"order.{row.kind}_confirmed")
        row.status, row.decided_by, row.decided_at = Status.CONFIRMED, actor, timezone.now()
        row.save(update_fields=["status", "decided_by", "decided_at"])
        record("update", model="finance.OrderPayment", object_id=row.pk, object_repr=f"{row.kind} {row.amount} {order.order_number}", actor=actor,
               event=f"payment.{row.kind}_confirmed")
        text = f"{'Payment' if row.kind == P.Kind.PAYMENT else 'Refund'} of {row.amount} was confirmed for order {order.order_number}."
        if order.customer_user:
            notify(order.customer_user, f"Order {order.order_number}", text)
        notify(order.workshop.owner, f"Order {order.order_number}", text)
        return row


def reject_payment(actor, payment_id: int, reason: str) -> OrderPayment:
    if not (actor.is_staff or actor.is_superuser):
        raise PermissionDenied("Only a platform administrator can reject payments.")
    if not reason.strip():
        raise err("reason", "Say why the payment is rejected.")
    with transaction.atomic():
        row = P.objects.select_for_update(of=("self",)).select_related("order__customer_user").get(pk=payment_id)
        if row.status != Status.PENDING:
            raise err("status", f"This payment is already {row.status}.")
        row.status, row.decided_by, row.decided_at, row.reject_reason = Status.REJECTED, actor, timezone.now(), reason.strip()[:255]
        row.save(update_fields=["status", "decided_by", "decided_at", "reject_reason"])
        record("update", model="finance.OrderPayment", object_id=row.pk, object_repr=f"{row.kind} {row.amount}", actor=actor, event=f"payment.{row.kind}_rejected")
        if row.order.customer_user:
            notify(row.order.customer_user, f"Order {row.order.order_number}", f"Your {row.kind} of {row.amount} was not accepted: {row.reject_reason}", "warning")
        return row


def summary(*, date_from=None, date_to=None, workshop_id=None) -> dict:
    """Figures for the administrators' report. Booked = accepted marketplace orders (accepted .. completed); collected = confirmed payments."""
    from django.db.models import Count, Sum

    booked_status = [Order.Status.CONFIRMED, Order.Status.IN_PRODUCTION, Order.Status.QUALITY_CHECK, Order.Status.READY, Order.Status.DELIVERY, Order.Status.DELIVERED]
    orders = Order.objects.filter(source=Order.Source.MARKETPLACE, status__in=booked_status)
    pays = P.objects.filter(status=Status.CONFIRMED)
    if date_from:
        orders, pays = orders.filter(created_at__date__gte=date_from), pays.filter(decided_at__date__gte=date_from)
    if date_to:
        orders, pays = orders.filter(created_at__date__lte=date_to), pays.filter(decided_at__date__lte=date_to)
    if workshop_id:
        orders, pays = orders.filter(workshop_id=workshop_id), pays.filter(order__workshop_id=workshop_id)
    z = Decimal("0.00")
    b = orders.aggregate(n=Count("id"), total=Sum("total_price"), commission=Sum("commission_amount"), payable=Sum("workshop_amount"))
    c = {k: pays.filter(kind=k).aggregate(n=Count("id"), amount=Sum("amount")) for k in (P.Kind.PAYMENT, P.Kind.REFUND)}
    pay_in, pay_out = c[P.Kind.PAYMENT]["amount"] or z, c[P.Kind.REFUND]["amount"] or z
    by_ws: dict[int, dict] = {}
    for o in orders.select_related("workshop").iterator():
        w = by_ws.setdefault(o.workshop_id, {"workshop": o.workshop_id, "name": o.workshop.name, "orders": 0, "total": z, "commission": z, "payable": z,
                                              "paid_so_far": z, "commission_covered": z, "payable_covered": z})
        w["orders"] += 1
        w["total"] += o.total_price
        w["commission"] += o.commission_amount
        w["payable"] += o.workshop_amount
        if o.payment_status != Order.PaymentStatus.REFUNDED and o.total_price > 0:
            share = o.paid_amount / o.total_price                         # money received so far covers the same share of both parts
            w["paid_so_far"] += o.paid_amount
            w["commission_covered"] += money(o.commission_amount * share)
            w["payable_covered"] += money(o.workshop_amount * share)
    return {"currency_note": "Amounts are in the currency of each order; this report adds them without conversion.",
            "booked": {"orders": b["n"], "total": b["total"] or z, "commission": b["commission"] or z, "workshop_amount": b["payable"] or z},
            "collected": {"payments": c[P.Kind.PAYMENT]["n"], "refunds": c[P.Kind.REFUND]["n"], "received": pay_in, "refunded": pay_out, "net": pay_in - pay_out},
            "by_workshop": sorted(by_ws.values(), key=lambda w: -w["total"]), "commission_percent_now": commission_percent(),
            "note": "Nothing here is a bank statement: it sums the order records and the payments an administrator confirmed by hand."}
