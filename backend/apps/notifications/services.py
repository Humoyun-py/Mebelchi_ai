from .models import Notification


def notify(user, title, body="", level="info"):
    if not user.notify_system:
        return None
    return Notification.objects.create(user=user, title=title, body=body, level=level)
