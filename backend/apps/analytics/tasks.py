from datetime import timedelta

from celery import shared_task
from django.core.management import call_command
from django.utils import timezone


@shared_task
def prune_system_logs(days: int = 30) -> int:
    from .models import SystemLog
    deleted, _ = SystemLog.objects.filter(created_at__lt=timezone.now() - timedelta(days=days)).delete()
    return deleted


@shared_task
def flush_expired_tokens() -> None:
    """Removes expired refresh tokens so the sessions table stays small."""
    call_command("flushexpiredtokens")
