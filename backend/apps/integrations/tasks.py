import logging

from celery import shared_task

from .models import TelegramLink
from .services import telegram_api_send

logger = logging.getLogger("mebelchi.telegram")


@shared_task(ignore_result=True)
def notify_user_on_telegram(user_id: int, title: str, body: str = ""):
    link = TelegramLink.objects.filter(user_id=user_id, user__is_active=True, user__notify_system=True).first()
    if link is None:
        return False
    text = f"{title}\n\n{body}".strip()
    return telegram_api_send(link.telegram_id, text)


@shared_task(ignore_result=True)
def broadcast_to_telegram(text: str) -> int:
    sent = 0
    for link in TelegramLink.objects.filter(user__is_active=True, user__notify_system=True).iterator():
        if telegram_api_send(link.telegram_id, text):
            sent += 1
    logger.info("Telegram broadcast delivered to %s chats", sent)
    return sent
