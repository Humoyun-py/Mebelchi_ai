"""Account linking and Telegram delivery.

Linking flow: the web user requests a code (valid 10 minutes, one active code at a time), then sends it to the bot.
The bot calls link_telegram() with the Telegram ID and the code. Failed attempts are counted per Telegram ID.
"""
import hmac
import logging
import re
import secrets
from datetime import timedelta
from hashlib import sha256

import httpx

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.notifications.services import notify

from .models import LinkCode, TelegramLink

logger = logging.getLogger("mebelchi.telegram")

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L: easy to read and type
CODE_LENGTH = 8
CODE_TTL = timedelta(minutes=10)
MAX_FAILED_ATTEMPTS = 5
FAILURE_WINDOW_SECONDS = 600


class LinkError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _keyed_hash(code: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), code.encode(), sha256).hexdigest()


def normalize_code(raw: str) -> str:
    return re.sub(r"[\s-]", "", raw or "").upper()


def create_link_code(user):
    """Return (display_code, expires_at). Any previously issued unused code for this user is invalidated."""
    now = timezone.now()
    with transaction.atomic():
        LinkCode.objects.filter(user=user, used_at__isnull=True).update(used_at=now)
        raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        expires_at = now + CODE_TTL
        LinkCode.objects.create(user=user, code_hash=_keyed_hash(raw), expires_at=expires_at)
    return f"{raw[:4]}-{raw[4:]}", expires_at


def _failure_key(telegram_id: int) -> str:
    return f"tg-link-fail:{telegram_id}"


def link_telegram(telegram_id: int, username: str, raw_code: str):
    """Redeem a code for a Telegram chat. Returns the linked user or raises LinkError."""
    if cache.get(_failure_key(telegram_id), 0) >= MAX_FAILED_ATTEMPTS:
        raise LinkError("too_many_attempts")
    code = normalize_code(raw_code)
    now = timezone.now()
    with transaction.atomic():
        lc = (LinkCode.objects.select_for_update()
              .select_related("user")
              .filter(code_hash=_keyed_hash(code), used_at__isnull=True)
              .first()) if len(code) == CODE_LENGTH else None
        if lc is None:
            _register_failure(telegram_id)
            raise LinkError("invalid_code")
        if lc.expires_at < now:
            _register_failure(telegram_id)
            raise LinkError("expired")
        user = lc.user
        if not user.is_active:
            raise LinkError("invalid_code")
        if TelegramLink.objects.filter(telegram_id=telegram_id).exclude(user=user).exists():
            raise LinkError("telegram_in_use")
        lc.used_at = now
        lc.save(update_fields=["used_at"])
        TelegramLink.objects.update_or_create(user=user, defaults={"telegram_id": telegram_id, "username": username[:64]})
    cache.delete(_failure_key(telegram_id))
    notify(user, "Telegram account linked", "Your Telegram chat is now connected to MEBELCHI AI. "
                                             "If this was not you, unlink it from Settings.")
    return user


def _register_failure(telegram_id: int) -> None:
    key = _failure_key(telegram_id)
    cache.add(key, 0, FAILURE_WINDOW_SECONDS)
    try:
        cache.incr(key)
    except ValueError:  # key expired between add and incr
        cache.set(key, 1, FAILURE_WINDOW_SECONDS)


def unlink_user(user) -> bool:
    deleted, _ = TelegramLink.objects.filter(user=user).delete()
    return bool(deleted)


def user_for_telegram(telegram_id: int):
    link = TelegramLink.objects.select_related("user").filter(telegram_id=telegram_id, user__is_active=True).first()
    return link.user if link else None


def telegram_api_send(chat_id: int, text: str) -> bool:
    """Send a plain-text message through the Telegram Bot API. Never raises."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.info("TELEGRAM_BOT_TOKEN is empty; skipping message to chat %s", chat_id)
        return False
    try:
        r = httpx.post(f"https://api.telegram.org/bot{token}/sendMessage",
                       json={"chat_id": chat_id, "text": text[:4000]}, timeout=5)
        if r.status_code != 200:
            logger.warning("Telegram sendMessage failed with HTTP %s", r.status_code)
            return False
        return True
    except httpx.HTTPError:
        logger.warning("Telegram sendMessage transport error")
        return False
