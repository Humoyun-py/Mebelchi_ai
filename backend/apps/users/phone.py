"""Phone verification: send a 6-digit code by SMS, then confirm it.

Rules: the code is random, stored only as a keyed hash, valid PHONE_CODE_TTL_SECONDS, usable once, and at most PHONE_CODE_MAX_ATTEMPTS wrong
guesses are accepted per code. A user may ask for a new code only every PHONE_CODE_RESEND_SECONDS and at most PHONE_CODE_MAX_PER_DAY times
a day. SMS that is not configured fails with 503 *before* anything is stored. A phone that already belongs to another verified account is refused.
"""
from __future__ import annotations

import hmac
import secrets
from datetime import timedelta
from hashlib import sha256

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from apps.audit.services import record
from apps.core import sms

from .models import PhoneVerification, User


class SmsUnavailable(APIException):
    status_code = 503
    default_detail = "SMS is not configured on this server, so phone numbers cannot be verified yet."
    default_code = "sms_unavailable"


class SmsFailed(APIException):
    status_code = 502
    default_detail = "The SMS could not be sent. Try again later."
    default_code = "sms_failed"


class TooManyRequests(APIException):
    status_code = 429
    default_code = "throttled"


def _hash(user_id: int, phone: str, code: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), f"{user_id}:{phone}:{code}".encode(), sha256).hexdigest()


def request_code(user: User, raw_phone: str) -> dict:
    sender = sms.get_sms()
    if not sender.enabled:
        raise SmsUnavailable()
    try:
        phone = sms.normalize_uz_phone(raw_phone)
    except sms.InvalidPhone as exc:
        raise ValidationError({"phone": str(exc)})
    if User.objects.filter(phone=phone, phone_verified_at__isnull=False).exclude(pk=user.pk).exists():
        raise ValidationError({"phone": "This phone number is already verified on another account."})
    now = timezone.now()
    ttl = settings.PHONE_CODE_TTL_SECONDS
    with transaction.atomic():
        User.objects.select_for_update().get(pk=user.pk)                 # serialises concurrent requests of one user
        recent = PhoneVerification.objects.filter(user=user, created_at__gte=now - timedelta(days=1))
        last = recent.first()
        wait = settings.PHONE_CODE_RESEND_SECONDS
        if last and (now - last.created_at).total_seconds() < wait:
            raise TooManyRequests(f"Wait {wait} seconds before asking for a new code.")
        if recent.count() >= settings.PHONE_CODE_MAX_PER_DAY:
            raise TooManyRequests("Too many codes were requested today. Try again tomorrow.")
        code = f"{secrets.randbelow(10**6):06d}"
        PhoneVerification.objects.filter(user=user, used_at__isnull=True).update(used_at=now)
        row = PhoneVerification.objects.create(user=user, phone=phone, code_hash=_hash(user.pk, phone, code), expires_at=now + timedelta(seconds=ttl))
        record("update", model="users.PhoneVerification", object_id=row.pk, object_repr=f"phone ...{phone[-4:]}", actor=user, event="phone.code_requested")
    try:
        sender.send(phone, f"Mebelchi AI: tasdiqlash kodi {code}. Kodni hech kimga bermang.")
    except (sms.SmsError, sms.SmsDisabled):
        PhoneVerification.objects.filter(pk=row.pk).update(used_at=timezone.now())      # an unsent code can never be used
        raise SmsFailed()
    return {"phone": phone, "expires_in": ttl, "resend_after": settings.PHONE_CODE_RESEND_SECONDS}


def confirm_code(user: User, raw_phone: str, code: str) -> User:
    try:
        phone = sms.normalize_uz_phone(raw_phone)
    except sms.InvalidPhone as exc:
        raise ValidationError({"phone": str(exc)})
    code = (code or "").strip()
    now = timezone.now()
    problem = None
    # Outcome is decided inside the transaction but raised AFTER it commits: raising inside would roll the attempt counter back
    # and a guesser would get unlimited tries.
    with transaction.atomic():
        row = PhoneVerification.objects.select_for_update().filter(user=user, phone=phone, used_at__isnull=True, expires_at__gt=now).first()
        if row is None:
            problem = "code"
        else:
            PhoneVerification.objects.filter(pk=row.pk).update(attempts=F("attempts") + 1)
            row.refresh_from_db()
            if row.attempts > settings.PHONE_CODE_MAX_ATTEMPTS:
                PhoneVerification.objects.filter(pk=row.pk).update(used_at=now)
                problem = "code"
            elif not (len(code) == 6 and code.isdigit() and hmac.compare_digest(row.code_hash, _hash(user.pk, phone, code))):
                problem = "code"
            else:
                try:
                    with transaction.atomic():
                        row.used_at = now
                        row.save(update_fields=["used_at"])
                        user.phone, user.phone_verified_at = phone, now
                        user.save(update_fields=["phone", "phone_verified_at"])
                except IntegrityError:
                    problem = "taken"
                else:
                    record("update", model="users.User", object_id=user.pk, object_repr=user.email, actor=user, event="phone.verified")
    if problem == "taken":
        raise ValidationError({"phone": "This phone number is already verified on another account."})
    if problem:
        raise ValidationError({"code": "The code is wrong or has expired."})
    return user
