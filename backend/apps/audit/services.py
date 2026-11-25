import logging

from django.db import transaction

from . import context
from .models import AuditLog

logger = logging.getLogger(__name__)


def record(action: str, *, model: str = "", object_id="", object_repr: str = "", changes: dict | None = None, actor=None, event: str = ""):
    """Writes one audit row. `actor` defaults to the authenticated user of the current request. Failures are logged and never raised into the caller.
    business logic *unless* the surrounding transaction fails: auditing problems are logged, not swallowed silently."""
    ctx = context.get_context()
    actor = actor if actor is not None else ctx.get("actor")
    try:
        with transaction.atomic():  # savepoint: a failed insert must not poison the caller's transaction (PostgreSQL)
            return AuditLog.objects.create(
                actor=actor, actor_email=(actor.email if actor else "")[:254], action=action, event=event[:40], model=model[:80],
                object_id=str(object_id)[:64], object_repr=(object_repr or "")[:200], changes=changes or {},
                ip=ctx.get("ip"), method=ctx.get("method", ""), path=ctx.get("path", ""))
    except Exception:  # an unwritable audit row must not take the user's request down, but it must be visible in the logs
        logger.exception("failed to write audit log (%s %s#%s)", action, model, object_id)
        return None


def save_with_event(obj, event: str, **save_kwargs):
    """`obj.save()` whose automatic audit row is labelled with a business event (e.g. "order.status_changed")."""
    obj._audit_event = event
    try:
        obj.save(**save_kwargs)
    finally:
        obj._audit_event = ""
    return obj
