import logging

from django.db import transaction

from .models import Notification

logger = logging.getLogger("mebelchi.notifications")


def notify(user, title, body="", level="info", order_id=None):
    if not user.notify_system:
        return None
    notification = Notification.objects.create(user=user, title=title, body=body, level=level)
    _push_to_telegram(user.id, title, body, order_id)
    return notification


def _push_to_telegram(user_id, title, body, order_id=None):
    """Mirror the notification to the user's linked Telegram chat, after the transaction commits.

    Failures never affect the request: the in-app notification already exists.
    """
    from apps.integrations.tasks import notify_user_on_telegram

    def dispatch():
        try:
            notify_user_on_telegram.delay(*((user_id, title, body, order_id) if order_id else (user_id, title, body)))
        except Exception:  # noqa: BLE001 - broker outages must not break user actions
            logger.exception("Could not queue Telegram notification for user %s", user_id)

    transaction.on_commit(dispatch)
