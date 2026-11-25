import hmac

from rest_framework.permissions import BasePermission

from django.conf import settings

BOT_HEADER = "HTTP_X_BOT_SECRET"


class IsTelegramBot(BasePermission):
    """Only the bot process holds TELEGRAM_BOT_API_SECRET. An empty secret disables every bot endpoint (fail closed)."""

    def has_permission(self, request, view):
        expected = settings.TELEGRAM_BOT_API_SECRET
        if not expected:
            return False
        provided = request.META.get(BOT_HEADER, "")
        return hmac.compare_digest(provided.encode(), expected.encode())
