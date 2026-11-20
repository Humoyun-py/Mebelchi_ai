from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from apps.users.models import User


def send_reset_email(email: str) -> None:
    """Silently does nothing for unknown emails (no account enumeration)."""
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if not user:
        return
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
    send_mail("Reset your MEBELCHI AI password",
              f"Hello {user.first_name},\n\nUse this link to set a new password:\n{link}\n\nIf you did not request this, ignore this email.",
              settings.DEFAULT_FROM_EMAIL, [user.email])


def resolve_reset(uid: str, token: str):
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        return None
    return user if default_token_generator.check_token(user, token) else None


def verify_google_credential(credential: str) -> dict | None:
    """Validates a Google Sign-In ID token with Google's tokeninfo endpoint. Returns the claims or None."""
    import json
    import urllib.parse
    import urllib.request

    if not settings.GOOGLE_CLIENT_ID or not credential or len(credential) > 4096:
        return None
    url = "https://oauth2.googleapis.com/tokeninfo?" + urllib.parse.urlencode({"id_token": credential})
    try:
        with urllib.request.urlopen(url, timeout=8) as r:  # noqa: S310 - fixed https host
            claims = json.loads(r.read().decode())
    except Exception:
        return None
    if claims.get("aud") != settings.GOOGLE_CLIENT_ID or str(claims.get("email_verified")).lower() != "true" or not claims.get("email"):
        return None
    if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        return None
    return claims
