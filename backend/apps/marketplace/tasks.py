"""Reminders for marketplace orders the workshop has not answered.

Every REMINDER_HOURS (default 4) the workshop owner is reminded; at most REMINDER_MAX (default 6, i.e. 24 hours) reminders are sent per order.
The reminders stop the moment the order leaves `pending` (accepted, rejected, cancelled). Each reminder is claimed with one conditional UPDATE, so two
workers, or a task that runs twice, can never send the same reminder twice. When the limit is reached the customer and the administrators are told
once, and nothing more is sent."""
import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db.models import F, Q
from django.utils import timezone

from apps.notifications.services import notify
from apps.users.models import User
from apps.workshops.models import Order

logger = logging.getLogger("mebelchi.marketplace")


def _limits():
    return int(getattr(settings, "ORDER_REMINDER_HOURS", 4)), int(getattr(settings, "ORDER_REMINDER_MAX", 6))


def due_orders(now=None):
    now = now or timezone.now()
    hours, maximum = _limits()
    cutoff = now - timedelta(hours=hours)
    return (Order.objects.filter(source=Order.Source.MARKETPLACE, status=Order.Status.PENDING, responded_at__isnull=True, reminders_sent__lt=maximum)
            .filter(Q(last_reminder_at__isnull=True, created_at__lte=cutoff) | Q(last_reminder_at__lte=cutoff))
            .select_related("workshop__owner", "customer_user"))


def send_reminders(now=None) -> int:
    now = now or timezone.now()
    hours, maximum = _limits()
    sent = 0
    for o in due_orders(now):
        claimed = Order.objects.filter(pk=o.pk, status=Order.Status.PENDING, responded_at__isnull=True, reminders_sent=o.reminders_sent).update(
            reminders_sent=F("reminders_sent") + 1, last_reminder_at=now)
        if claimed != 1:
            continue                                                  # another worker got it, or the order was answered in the meantime
        n = o.reminders_sent + 1
        left = maximum - n
        notify(o.workshop.owner, f"Reminder: order {o.order_number}",
               f"{o.title} is waiting for your answer (reminder {n} of {maximum}). Please accept or reject it.", "warning")
        sent += 1
        if n == maximum:
            if o.customer_user:
                notify(o.customer_user, f"Order {o.order_number}", f"{o.workshop.name} has not answered in {hours * maximum} hours. You can cancel the order and choose another workshop.", "warning")
            for admin in User.objects.filter(is_staff=True, is_active=True):
                notify(admin, f"Unanswered order {o.order_number}", f"{o.workshop.name} did not answer for {hours * maximum} hours.", "warning")
        logger.info("order %s reminder %s/%s (%s left)", o.order_number, n, maximum, left)
    return sent


@shared_task(name="apps.marketplace.tasks.remind_pending_orders")
def remind_pending_orders() -> int:
    return send_reminders()
