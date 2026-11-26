"""Catalogue rules: who may add or change an item, validation of its sizes, duplicates, approval. Views stay thin."""
from __future__ import annotations

import re

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils.text import slugify
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.audit.services import record, save_with_event
from apps.calculations import engine
from apps.workshops import access
from apps.workshops.models import Workshop

from .models import FurnitureTemplate as T
from .seed_data import CATEGORIES

CATEGORY_SLUGS = {c["slug"] for c in CATEGORIES}
SIZE_KEYS = ("width", "height", "depth", "thickness", "shelves", "doors", "drawers")
# Changing these changes WHAT the item is, so an approved item goes back to review. Price, stock and wording do not.
REVIEW_FIELDS = {"name", "category", "defaults", "glb_file"}
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def err(field: str, msg: str):
    return ValidationError({field: msg})


def staff(user) -> bool:
    return bool(user.is_staff or user.is_superuser)


def my_workshop_ids(user) -> list[int]:
    return list(access.owner_workshop_ids(user).values_list("workshop_id", flat=True))


def visible(user):
    """Approved items for everybody; own workshops' items in any state; staff see everything. Removed items are never listed."""
    qs = T.objects.filter(is_active=True).select_related("workshop").prefetch_related("images")
    if staff(user):
        return qs
    return qs.filter(Q(status=T.Status.APPROVED) | Q(workshop_id__in=my_workshop_ids(user)))


def can_manage(user, item: T) -> bool:
    return staff(user) or (item.workshop_id is not None and access.is_owner(user, item.workshop_id))


def require_manage(user, item: T):
    if not can_manage(user, item):
        raise PermissionDenied("Only the workshop that owns this item (or a platform administrator) can change it.")
    if item.workshop_id and not staff(user):
        access.require_writable(item.workshop)


def clean_defaults(data: dict) -> dict:
    """Sizes through the cabinet engine, so the catalogue can never hold a cabinet that cannot be built."""
    if not isinstance(data, dict):
        raise err("defaults", "must be an object")
    out = {k: data[k] for k in SIZE_KEYS if k in data}
    missing = [k for k in ("width", "height", "depth") if k not in out]
    if missing:
        raise ValidationError({k: "is required" for k in missing})
    try:
        engine.validate(engine.CabinetInput.from_dict({"thickness": 18, **out}))
    except engine.EngineValidationError as e:
        raise ValidationError(dict(e.errors))
    except (TypeError, ValueError):
        raise err("defaults", "sizes must be numbers")
    out.setdefault("thickness", 18)
    for k in ("shelves", "doors", "drawers"):
        out.setdefault(k, 0)
    return out


def make_dedup_key(category: str, name: str, defaults: dict) -> str:
    n = re.sub(r"\s+", " ", name.strip().lower())
    return f"{category}|{n}|{defaults.get('width')}x{defaults.get('height')}x{defaults.get('depth')}"[:200]


def _unique_slug(base: str) -> str:
    base = (slugify(base) or "item")[:60]
    slug, i = base, 2
    while T.objects.filter(slug=slug).exists():
        slug, i = f"{base}-{i}", i + 1
    return slug


def _check_fields(data: dict):
    if "category" in data and data["category"] not in CATEGORY_SLUGS:
        raise err("category", f"must be one of: {', '.join(sorted(CATEGORY_SLUGS))}")
    if data.get("color") and not HEX.match(data["color"]):
        raise err("color", "must be a hex colour like #c9a27a")
    if data.get("price") is not None and data["price"] < 0:
        raise err("price", "cannot be negative")


def _duplicate_error():
    return ValidationError({"name": "This workshop already has an item with the same category, name and size."})


def create_item(user, data: dict) -> T:
    data = dict(data)
    ws = data.pop("workshop", None)
    _check_fields(data)
    if ws is None:
        if not staff(user):
            raise err("workshop", "Choose the workshop this item belongs to.")
        status = T.Status.APPROVED
    else:
        if not (staff(user) or access.is_owner(user, ws.pk)):
            raise PermissionDenied("Only the owner of the workshop can add items to its catalogue.")
        if ws.status != Workshop.Status.ACTIVE:
            access.require_writable(ws)
        status = T.Status.APPROVED if staff(user) else T.Status.PENDING
    defaults = clean_defaults(data.pop("defaults"))
    key = make_dedup_key(data["category"], data["name"], defaults) if ws else ""
    slug = _unique_slug(f"{ws.slug}-{data['name']}" if ws else data["name"])
    try:
        with transaction.atomic():
            item = T(slug=slug, workshop=ws, created_by=user, status=status, defaults=defaults, dedup_key=key, **data)
            return save_with_event(item, "catalog.created")
    except IntegrityError:
        raise _duplicate_error()


def update_item(user, item: T, data: dict) -> T:
    require_manage(user, item)
    data = dict(data)
    data.pop("workshop", None)
    _check_fields(data)
    if "defaults" in data:
        data["defaults"] = clean_defaults({**item.defaults, **data["defaults"]})
    changed_identity = any(k in data and data[k] != getattr(item, k) for k in REVIEW_FIELDS)
    for k, v in data.items():
        setattr(item, k, v)
    if item.workshop_id:
        item.dedup_key = make_dedup_key(item.category, item.name, item.defaults)
    if changed_identity and item.workshop_id and not staff(user) and item.status != T.Status.PENDING:
        item.status, item.review_note = T.Status.PENDING, ""
    try:
        with transaction.atomic():
            return save_with_event(item, "catalog.updated")
    except IntegrityError:
        raise _duplicate_error()


def deactivate_item(user, item: T):
    require_manage(user, item)
    item.is_active = False
    save_with_event(item, "catalog.removed")


def review_item(actor, item: T, target: str, note: str = "") -> T:
    if not staff(actor):
        raise PermissionDenied("Only a platform administrator can approve catalogue items.")
    if target not in (T.Status.APPROVED, T.Status.REJECTED):
        raise err("status", "must be approved or rejected")
    if target == T.Status.REJECTED and not note.strip():
        raise err("note", "Say why the item was rejected.")
    with transaction.atomic():
        item = T.objects.select_for_update().get(pk=item.pk)
        item.status, item.review_note = target, "" if target == T.Status.APPROVED else note.strip()[:500]
        return save_with_event(item, f"catalog.{target}")


def get_visible(user, pk) -> T:
    item = visible(user).filter(pk=pk).first()
    if item is None:
        raise NotFound()
    return item


def touch(item: T, event: str):
    """A change that does not alter the item row itself (an image): bump `updated_at` and write an audit row."""
    item.save(update_fields=["updated_at"])
    record("update", model="furniture.FurnitureTemplate", object_id=item.pk, object_repr=item.name, event=event)
