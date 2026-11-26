"""Room-design service: the layer between the pure state machine (apps.conversations.flow), the pure geometry
(apps.geometry.room) and the database. The REST API (views.py) and, later, the Telegram bot both go through here.

Rules
- A flow belongs to one user; every operation locks the flow row, so two requests for the same flow are applied one after the other.
- The conversation state lives in RoomFlow (`step`, `answers`); the 3D room lives in the linked Design (`config`, schema room.v1).
- Answering `style` builds (or rebuilds) the room: furniture picked in `elements` is laid out by the deterministic auto-placer.
  Manual placements are therefore replaced when the user goes back and answers `style` again; this is stated in the API docs.
- Nothing here analyses photos or calls an external service. Layouts are planning aids, not verified for manufacture.
"""
from __future__ import annotations

from django.db import transaction

from apps.conversations import flow
from apps.designs.models import Design
from apps.designs.presets import STYLES
from apps.furniture.models import FurnitureTemplate
from apps.galleries.models import GalleryImage
from apps.geometry import room as geo

from . import legacy, mebelchi
from .models import RoomFlow

SCHEMA = "room.v1"
MAX_ACTIVE_FLOWS = 20
FLOOR_COLOR = "#d6c9b4"
ITEM_FIELDS = {"x", "z", "rot", "width", "depth", "height", "shelves", "doors", "drawers", "color", "name"}


class NotFound(Exception):
    pass


def context() -> flow.FlowContext:
    rows = FurnitureTemplate.objects.filter(is_active=True, status=FurnitureTemplate.Status.APPROVED).order_by("category", "name")
    return flow.FlowContext(templates=[{"slug": t.slug, "category": t.category, "name": t.name, "defaults": t.defaults} for t in rows])


def state_of(f: RoomFlow) -> dict:
    return {"step": f.step, "answers": f.answers or {}}


def _lock(user, pk: int) -> RoomFlow:
    f = RoomFlow.objects.select_for_update(of=("self",)).select_related("design").filter(pk=pk, owner=user).first()
    if f is None:
        raise NotFound
    return f


def _style(style_id: str) -> dict:
    return next(s for s in STYLES if s["id"] == style_id)


def _colors(config: dict) -> dict:
    return config.get("colors") or {"wall": "#cbd5e1", "floor": FLOOR_COLOR, "item": "#e5e7eb"}


# ------------------------------------------------------------------------------------------------ conversation

def start(user) -> RoomFlow:
    with transaction.atomic():
        if RoomFlow.objects.filter(owner=user, status=RoomFlow.Status.ACTIVE).count() >= MAX_ACTIVE_FLOWS:
            raise flow.FlowError(f"You have {MAX_ACTIVE_FLOWS} unfinished room designs. Finish or delete one first.")
        s = flow.initial()
        return RoomFlow.objects.create(owner=user, step=s["step"], answers=s["answers"])


def answer(user, pk: int, step: str, value) -> RoomFlow:
    with transaction.atomic():
        f = _lock(user, pk)
        _require_active(f)
        ctx = context()
        photo = None
        if step == "photo" and isinstance(value, dict) and isinstance(value.get("image_id"), int) and not isinstance(value.get("image_id"), bool):
            photo = GalleryImage.objects.filter(pk=value["image_id"], owner=user).first()
            if photo is None:
                raise flow.FlowValidationError({"image_id": "Image not found."})
        new = flow.apply_answer(state_of(f), step, value, ctx)
        if step == "photo":
            f.photo = photo
        if new["step"] == "generate":
            f.design = _build_design(f, user, new["answers"], ctx)
            new = flow.to_furnish(new)
        f.step, f.answers = new["step"], new["answers"]
        f.save()
        return f


def back(user, pk: int) -> RoomFlow:
    with transaction.atomic():
        f = _lock(user, pk)
        _require_active(f)
        new = flow.back(state_of(f))
        f.step, f.answers = new["step"], new["answers"]
        f.save()
        return f


def finish(user, pk: int) -> RoomFlow:
    with transaction.atomic():
        f = _lock(user, pk)
        _require_active(f)
        _require_furnish(f)
        new = flow.finish(state_of(f))
        f.step, f.answers, f.status = new["step"], new["answers"], RoomFlow.Status.COMPLETED
        f.save()
        return f


def delete(user, pk: int) -> None:
    with transaction.atomic():
        _lock(user, pk).delete()                      # the Design, if any, is the user's saved work and stays


def import_legacy(user, design_id: int) -> tuple[RoomFlow, bool]:
    """Opens an old interior design in the room designer. Returns (flow, created).

    The old design is never changed or deleted: the room designer works on a COPY (same name, project and photo) whose config is room.v1 and
    keeps the old config under `legacy`. Calling this again for the same design returns the same flow, so it can be retried safely."""
    with transaction.atomic():
        src = Design.objects.select_for_update().filter(pk=design_id, owner=user, kind=Design.Kind.INTERIOR).first()
        if src is None:
            raise NotFound
        existing = RoomFlow.objects.filter(owner=user).filter(design_id=src.pk).first() or \
            RoomFlow.objects.filter(owner=user, design__config__migrated_from=src.pk).select_related("design").first()
        if existing is not None:
            return existing, False
        if legacy.is_room_design(src.config):
            raise flow.FlowError("This design is already in the room-designer format but has no conversation to open.")
        if RoomFlow.objects.filter(owner=user, status=RoomFlow.Status.ACTIVE).count() >= MAX_ACTIVE_FLOWS:
            raise flow.FlowError(f"You have {MAX_ACTIVE_FLOWS} unfinished room designs. Finish or delete one first.")
        photo = src.room_image if src.room_image_id and src.room_image.owner_id == user.id else None
        out = legacy.convert(src.config, context().templates, photo.pk if photo else None)
        out["config"]["migrated_from"] = src.pk
        d = Design.objects.create(owner=user, project=src.project, kind=Design.Kind.INTERIOR, name=src.name, config=out["config"], room_image=photo)
        return RoomFlow.objects.create(owner=user, step="furnish", answers=out["answers"], design=d, photo=photo), True


def _require_active(f: RoomFlow):
    if f.status != RoomFlow.Status.ACTIVE:
        raise flow.FlowError("This room design is finished and can no longer be changed.")


def _require_furnish(f: RoomFlow):
    if f.step != "furnish" or f.design_id is None:
        raise flow.FlowError(f"Furniture can only be changed in the 'furnish' step; the current step is '{f.step}'.")


# ------------------------------------------------------------------------------------------------ the 3D room

def _layout(answers: dict, ctx: flow.FlowContext) -> tuple[list[dict], list[dict]]:
    wanted = (answers.get("elements") or {}).get("furniture", [])
    by_slug = {t["slug"]: t for t in ctx.templates}
    chosen = [by_slug[s] for s in wanted if s in by_slug]
    return geo.suggest_layout(chosen, answers["size"], answers.get("openings", []), _style(answers["style"])["furniture"])


def _build_design(f: RoomFlow, user, answers: dict, ctx: flow.FlowContext) -> Design:
    style = _style(answers["style"])
    items, warnings = _layout(answers, ctx)
    config = {"schema": SCHEMA, "goal": answers["goal"], "style": style["id"], "room": answers["size"], "openings": answers.get("openings", []),
              "items": items, "not_placed": [w for w in warnings if w["code"] == "not_placed"],
              "colors": {"wall": style["wall"], "floor": FLOOR_COLOR, "item": style["furniture"]}}
    photo = f.photo if f.photo_id else None
    if f.design_id:
        d = Design.objects.select_for_update().get(pk=f.design_id)
        d.config, d.room_image = config, photo
        d.save(update_fields=["config", "room_image", "updated_at"])
        return d
    size = answers["size"]
    name = f"{answers['goal'].capitalize()} {size['width'] / 1000:g} x {size['length'] / 1000:g} m"
    return Design.objects.create(owner=user, kind=Design.Kind.INTERIOR, name=name[:160], config=config, room_image=photo)


def room_view(f: RoomFlow) -> dict | None:
    """The room as the client needs it: config + current warnings. None before the room is built."""
    if not f.design_id:
        return None
    c = f.design.config
    return {"config": c, "warnings": geo.layout_warnings(c["room"], c.get("openings", []), c.get("items", [])) + list(c.get("not_placed", []))}


def model(f: RoomFlow) -> dict:
    if not f.design_id:
        raise flow.FlowError("The 3D room is not built yet.")
    c = f.design.config
    col = _colors(c)
    return geo.build_room(c, col["wall"], col["floor"], col["item"])


# ------------------------------------------------------------------------------------------------ furnishing

def _design_locked(f: RoomFlow) -> Design:
    return Design.objects.select_for_update().get(pk=f.design_id)


def add_item(user, pk: int, data: dict) -> tuple[RoomFlow, dict, list[dict]]:
    with transaction.atomic():
        f = _lock(user, pk)
        _require_active(f)
        _require_furnish(f)
        d = _design_locked(f)
        c = d.config
        if not isinstance(data, dict):
            raise geo.RoomError({"item": "must be an object"})
        unknown = set(data) - ITEM_FIELDS - {"template"}
        if unknown:
            raise geo.RoomError({k: "is not a recognised field" for k in sorted(unknown)})
        t = next((t for t in context().templates if t["slug"] == data.get("template")), None)
        if t is None:
            raise geo.RoomError({"template": "must be the id of an available furniture template"})
        if len(c["items"]) >= geo.MAX_ITEMS:
            raise geo.RoomError({"items": f"at most {geo.MAX_ITEMS} items"})
        base = {"template": t["slug"], "name": t["name"], "width": t["defaults"]["width"], "depth": t["defaults"]["depth"], "height": t["defaults"]["height"],
                "shelves": t["defaults"].get("shelves", 0), "doors": t["defaults"].get("doors", 0), "drawers": t["defaults"].get("drawers", 0),
                "color": _colors(c)["item"]}
        if t["defaults"].get("thickness", 18) != 18:
            base["thickness"] = t["defaults"]["thickness"]
        base.update({k: v for k, v in data.items() if k != "template"})
        if "x" in data and "z" in data:
            item, warnings = geo.validate_item(base, c["room"], c["items"], c.get("openings", []))
        else:
            placed = geo.auto_place(base, c["room"], c["items"], c.get("openings", []))
            if placed is None:
                raise geo.RoomError({"position": "this item does not fit anywhere in the room; make room or pick a smaller size"})
            item, warnings = placed
        c["items"].append(item)
        _save(f, d, c)
        return f, item, warnings


def update_item(user, pk: int, item_id: str, data: dict) -> tuple[RoomFlow, dict, list[dict]]:
    with transaction.atomic():
        f = _lock(user, pk)
        _require_active(f)
        _require_furnish(f)
        d = _design_locked(f)
        c = d.config
        if not isinstance(data, dict) or not data:
            raise geo.RoomError({"item": "send the fields to change"})
        unknown = set(data) - ITEM_FIELDS
        if unknown:
            raise geo.RoomError({k: "cannot be changed" if k in ("id", "template") else "is not a recognised field" for k in sorted(unknown)})
        current = next((i for i in c["items"] if i["id"] == item_id), None)
        if current is None:
            raise NotFound
        others = [i for i in c["items"] if i["id"] != item_id]
        item, warnings = geo.validate_item({**current, **data}, c["room"], others, c.get("openings", []))
        c["items"] = [item if i["id"] == item_id else i for i in c["items"]]
        _save(f, d, c)
        return f, item, warnings


def remove_item(user, pk: int, item_id: str) -> RoomFlow:
    with transaction.atomic():
        f = _lock(user, pk)
        _require_active(f)
        _require_furnish(f)
        d = _design_locked(f)
        c = d.config
        if not any(i["id"] == item_id for i in c["items"]):
            raise NotFound
        c["items"] = [i for i in c["items"] if i["id"] != item_id]
        _save(f, d, c)
        return f


def reset_layout(user, pk: int) -> RoomFlow:
    """Throws away manual placements and lays the furniture chosen in `elements` out again."""
    with transaction.atomic():
        f = _lock(user, pk)
        _require_active(f)
        _require_furnish(f)
        d = _design_locked(f)
        c = d.config
        items, warnings = _layout(f.answers, context())
        c["items"], c["not_placed"] = items, [w for w in warnings if w["code"] == "not_placed"]
        _save(f, d, c)
        return f


def _save(f: RoomFlow, d: Design, config: dict):
    d.config = config
    d.save(update_fields=["config", "updated_at"])
    f.design = d                                      # the caller returns `f`: it must show the new config, not the one loaded before
    f.save(update_fields=["updated_at"])


# ------------------------------------------------------------------------------------------------ settings, export, import

def update_settings(user, pk: int, data: dict) -> RoomFlow:
    """Wall / floor colour, floor material, light and camera of the 3D room. Colours change the look only, never the geometry."""
    with transaction.atomic():
        f = _lock(user, pk)
        _require_active(f)
        _require_furnish(f)
        if not isinstance(data, dict) or not data:
            raise geo.RoomError({"settings": "send the settings to change"})
        unknown = set(data) - {"wall", "floor", "floor_material", "light", "camera"}
        if unknown:
            raise geo.RoomError({k: "is not a recognised setting" for k in sorted(unknown)})
        d = _design_locked(f)
        c = d.config
        errors: dict[str, str] = {}
        colors = dict(_colors(c))
        for k in ("wall", "floor"):
            if k in data:
                if isinstance(data[k], str) and geo.HEX.match(data[k]):
                    colors[k] = data[k]
                else:
                    errors[k] = "must be a hex colour like #c9a27a"
        if "floor_material" in data:
            if data["floor_material"] in mebelchi.FLOOR_MATERIALS:
                c["floor_material"] = data["floor_material"]
            else:
                errors["floor_material"] = f"must be one of: {', '.join(mebelchi.FLOOR_MATERIALS)}"
        if "light" in data:
            c["light"] = mebelchi.validate_light(data["light"], errors) or c.get("light")
        if "camera" in data:
            c["camera"] = mebelchi.validate_camera(data["camera"], errors) or c.get("camera")
        if errors:
            raise geo.RoomError(errors)
        c["colors"] = colors
        _save(f, d, c)
        return f


def export_project(user, pk: int) -> tuple[str, dict]:
    f = RoomFlow.objects.select_related("design").filter(pk=pk, owner=user).first()
    if f is None:
        raise NotFound
    if not f.design_id:
        raise flow.FlowError("The 3D room is not built yet, so there is nothing to export.")
    return f.design.name, mebelchi.build(f.design.name, f.design.config)


def export_glb(user, pk: int) -> tuple[str, bytes]:
    from apps.geometry import exporters
    f = RoomFlow.objects.select_related("design").filter(pk=pk, owner=user).first()
    if f is None:
        raise NotFound
    return f.design.name if f.design_id else "room", exporters.to_glb(model(f)["boxes"])


def import_project(user, raw) -> tuple[RoomFlow, list[str]]:
    """Creates a new room design from a .mebelchi file. Returns (flow, catalogue ids in the file that this server does not know)."""
    parsed = mebelchi.parse(raw)
    cfg = parsed["config"]
    ctx = context()
    known = {t["slug"] for t in ctx.templates}
    wanted = sorted({i["template"] for i in cfg["items"] if i.get("template")})
    unknown = [s for s in wanted if s not in known]
    with transaction.atomic():
        if RoomFlow.objects.filter(owner=user, status=RoomFlow.Status.ACTIVE).count() >= MAX_ACTIVE_FLOWS:
            raise flow.FlowError(f"You have {MAX_ACTIVE_FLOWS} unfinished room designs. Finish or delete one first.")
        allowed = {t["slug"] for t in ctx.allowed_templates(cfg["goal"])}
        answers = {"goal": cfg["goal"], "photo": {"skipped": True},
                   "elements": {"doors": sum(o["type"] == "door" for o in cfg["openings"]), "windows": sum(o["type"] == "window" for o in cfg["openings"]),
                                "furniture": [s for s in wanted if s in allowed]},
                   "size": cfg["room"], "openings": cfg["openings"], "style": cfg["style"]}
        d = Design.objects.create(owner=user, kind=Design.Kind.INTERIOR, name=parsed["name"], config=cfg)
        return RoomFlow.objects.create(owner=user, step="furnish", answers=answers, design=d), unknown
