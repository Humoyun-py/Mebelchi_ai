"""Automatic create / update / delete records for the models listed in TRACKED.

Limits (by design of Django signals): `QuerySet.update()`, `bulk_create()` and raw SQL do not send signals and are not recorded; call
`services.record()` explicitly where such a bulk change matters."""
import datetime
import decimal
import json

from django.apps import apps
from django.db import models
from django.db.models.signals import post_save, pre_delete, pre_save

from . import services
from .models import AuditLog

# app_label.Model -> fields that are never written to the log with their values
TRACKED: dict[str, set[str]] = {
    "users.User": {"password", "last_login"},
    "workspaces.Folder": set(),
    "projects.Project": set(),
    "materials.Material": set(),
    "calculations.Calculation": {"result"},
    "cutting_lists.CuttingList": set(),
    "designs.Design": set(),
    "galleries.GalleryImage": set(),
    "files.UserFile": set(),
    "conversations.Conversation": set(),
    "subscriptions.Plan": set(),
    "subscriptions.Subscription": set(),
    "subscriptions.Payment": set(),
    "analytics.FeatureFlag": set(),
    "workshops.Workshop": set(),
    "workshops.WorkshopMember": set(),
    # customer contact details are personal data: the log shows that they changed, not their values
    "workshops.Order": {"customer_phone", "customer_email", "customer_address"},
    "workshops.Task": set(),
}
SENSITIVE_WORDS = ("password", "token", "secret", "api_key")
MAX_VALUE_LEN = 200
IGNORED_FIELDS = {"last_login"}


def _redacted(name: str, hidden: set[str]) -> bool:
    return name in hidden or any(w in name for w in SENSITIVE_WORDS)


def _plain(value):
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, (dict, list)):
        text = json.dumps(value, default=str, ensure_ascii=False)
        return text if len(text) <= MAX_VALUE_LEN else text[:MAX_VALUE_LEN] + "…"
    text = str(value)
    return text if len(text) <= MAX_VALUE_LEN else text[:MAX_VALUE_LEN] + "…"


def _auditable_fields(instance):
    for f in instance._meta.concrete_fields:
        if isinstance(f, models.DateTimeField) and (f.auto_now or f.auto_now_add):
            continue  # bookkeeping timestamps change on every save
        if f.name in IGNORED_FIELDS or f.primary_key:
            continue
        yield f


def _diff(old, new, hidden: set[str]) -> dict:
    changes = {}
    for f in _auditable_fields(new):
        a, b = f.value_from_object(old), f.value_from_object(new)
        if a == b:
            continue
        changes[f.name] = ({"old": "[redacted]", "new": "[redacted]"} if _redacted(f.name, hidden) else {"old": _plain(a), "new": _plain(b)})
    return changes


def _label(instance) -> str:
    return instance._meta.label_lower


def _repr(instance) -> str:
    try:
        return str(instance)
    except Exception:  # a broken __str__ must not block the delete
        return f"{instance._meta.object_name} #{instance.pk}"


def _before_save(sender, instance, raw=False, **kwargs):
    if raw:
        return
    instance._audit_changes = None
    if instance.pk and not instance._state.adding:
        old = sender._default_manager.filter(pk=instance.pk).first()
        if old is not None:
            instance._audit_changes = _diff(old, instance, TRACKED[sender._meta.label])


def _after_save(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    if created:
        services.record(AuditLog.Action.CREATE, model=_label(instance), object_id=instance.pk, object_repr=_repr(instance),
                        event=getattr(instance, "_audit_event", ""))
        return
    changes = getattr(instance, "_audit_changes", None)
    if changes:  # nothing recorded for a save that changed no business field
        services.record(AuditLog.Action.UPDATE, model=_label(instance), object_id=instance.pk, object_repr=_repr(instance), changes=changes,
                        event=getattr(instance, "_audit_event", ""))


def _before_delete(sender, instance, **kwargs):
    services.record(AuditLog.Action.DELETE, model=_label(instance), object_id=instance.pk, object_repr=_repr(instance),
                    event=getattr(instance, "_audit_event", ""))


def connect():
    for label in TRACKED:
        model = apps.get_model(label)
        uid = f"audit.{label}"
        pre_save.connect(_before_save, sender=model, dispatch_uid=uid + ".pre_save")
        post_save.connect(_after_save, sender=model, dispatch_uid=uid + ".post_save")
        pre_delete.connect(_before_delete, sender=model, dispatch_uid=uid + ".pre_delete")
