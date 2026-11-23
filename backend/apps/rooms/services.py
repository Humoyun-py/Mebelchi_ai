"""Room-flow use cases shared by the web API and the Telegram bot endpoints.

Views stay thin: they authenticate, find the user, call a function here. Ownership is enforced by `get_flow`
(another user's flow is a 404, never a 403, so existence is not revealed).
"""
from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.http import Http404
from PIL import Image
from rest_framework.exceptions import APIException, ValidationError

from apps.analytics.services import track
from apps.conversations import flow as flow_mod
from apps.designs.models import Design
from apps.designs.presets import STYLES
from apps.furniture.models import FurnitureTemplate
from apps.galleries.models import GalleryImage
from apps.geometry import room as geo
from apps.subscriptions.services import enforce_storage_limit

from .models import RoomFlow

SCHEMA = "room.v1"
DISCLAIMER = "Visual layout for planning. Not verified for manufacture; needs professional review."
ITEM_FIELDS = ("template", "name", "x", "z", "rot", "width", "depth", "height", "shelves", "doors", "drawers", "thickness", "color")


class Conflict(APIException):
    status_code = 409
    default_detail = "Conflict."

    def __init__(self, detail=None, code=None):
        super().__init__(detail, code)
        self.detail = detail  # DRF would turn every value into a string; clients need current_rev as a number


def _conflict(code: str, message: str, **extra) -> Conflict:
    return Conflict({"detail": message, "code": code, **extra})


# ------------------------------------------------------------------------------------------------ lookup

def catalog_context() -> flow_mod.FlowContext:
    return flow_mod.FlowContext(templates=[{"slug": t.slug, "category": t.category, "name": t.name, "defaults": t.defaults}
                                           for t in FurnitureTemplate.objects.filter(is_active=True)])


def get_flow(user, pk) -> RoomFlow:
    flow = RoomFlow.objects.filter(pk=pk, owner=user).select_related("design", "photo").first()
    if flow is None:
        raise Http404
    return flow


def active_for(user) -> RoomFlow | None:
    return RoomFlow.objects.filter(owner=user, status=RoomFlow.Status.ACTIVE).select_related("design", "photo").first()


def _state(flow: RoomFlow) -> dict:
    return {"step": flow.step, "answers": flow.answers or {}}


def _store(flow: RoomFlow, state: dict, **fields):
    flow.step, flow.answers = state["step"], state["answers"]
    for k, v in fields.items():
        setattr(flow, k, v)
    flow.save()


def _config(flow: RoomFlow) -> dict:
    if flow.design_id is None:
        raise _conflict("not_generated", "The 3D room is created after the style step.")
    return flow.design.config


def view(flow: RoomFlow, warnings: list | None = None) -> dict:
    """The full state a client needs: where the user is, what to ask next, and (when it exists) the room's items."""
    d = flow_mod.describe(_state(flow), catalog_context())
    out = {"id": flow.id, "status": flow.status, "step": flow.step, "descriptor": d, "answers": flow.answers,
           "design_id": flow.design_id, "photo_id": flow.photo_id, "rev": None, "created_at": flow.created_at, "updated_at": flow.updated_at,
           "warnings": warnings or []}
    if flow.design_id:
        cfg = flow.design.config
        out["rev"] = cfg["rev"]
        out["items"] = cfg["items"]
        out["openings"] = cfg["openings"]
        out["room"] = cfg["room"]
        out["style"] = cfg["style"]
    return out


# ------------------------------------------------------------------------------------------------ conversation

def start(user) -> RoomFlow:
    flow = RoomFlow.objects.create(owner=user)
    track(user, "room_flow_started")
    return flow


def start_or_resume(user, new: bool = False) -> tuple[RoomFlow, bool]:
    """Bot entry point: continue the latest active flow, or start one. Returns (flow, created)."""
    flow = None if new else active_for(user)
    if new:
        RoomFlow.objects.filter(owner=user, status=RoomFlow.Status.ACTIVE).update(status=RoomFlow.Status.ABANDONED)
    if flow is not None:
        return flow, False
    return start(user), True


def _require_active(flow: RoomFlow):
    if flow.status != RoomFlow.Status.ACTIVE:
        raise _conflict("not_active", f"This room flow is {flow.status}.", status=flow.status)


def _image_for(user, image_id: int) -> GalleryImage:
    img = GalleryImage.objects.filter(pk=image_id, owner=user).first()
    if img is None:  # same answer for "missing" and "someone else's", so ids cannot be probed
        raise ValidationError({"image_id": "Image not found."})
    return img


@transaction.atomic
def answer(flow: RoomFlow, step: str, value) -> dict:
    _require_active(flow)
    state = _state(flow)
    ctx = catalog_context()
    try:
        new = flow_mod.apply_answer(state, step, value, ctx)
    except flow_mod.StepMismatch as e:
        raise _conflict("step_mismatch", str(e), expected=e.expected)
    except flow_mod.FlowValidationError as e:
        raise ValidationError(e.errors)
    except flow_mod.FlowError as e:
        raise _conflict("not_answerable", str(e))
    photo, fields, warnings = flow.photo, {}, []
    if step == "photo":  # validated as a shape by the flow; ownership is checked here, after the step itself is known to be right
        image_id = new["answers"]["photo"].get("image_id")
        photo = _image_for(flow.owner, image_id) if image_id else None
        fields["photo"] = photo
    if new["step"] == "generate":
        warnings, reset = _generate(flow, new, ctx, photo)
        new = flow_mod.to_furnish(new)
        if reset:
            warnings.append({"code": "items_reset", "message": "The room was rebuilt, so previously placed furniture was replaced by a new suggestion."})
    if new["step"] == "done":
        fields["status"] = RoomFlow.Status.COMPLETED
        track(flow.owner, "room_flow_completed", items=len(flow.design.config["items"]) if flow.design_id else 0)
    _store(flow, new, **fields)
    return view(flow, warnings)


def _generate(flow: RoomFlow, state: dict, ctx: flow_mod.FlowContext, photo) -> tuple[list, bool]:
    a = state["answers"]
    room, openings = a["size"], a["openings"]
    style = next(s for s in STYLES if s["id"] == a["style"])
    by_slug = {t["slug"]: t for t in ctx.templates}
    chosen = [by_slug[s] for s in a["elements"]["furniture"] if s in by_slug]
    items, warnings = geo.suggest_layout(chosen, room, openings, style["furniture"])
    previous = flow.design.config if flow.design_id else None
    config = {"schema": SCHEMA, "rev": (previous["rev"] + 1) if previous else 1, "goal": a["goal"], "style": a["style"],
              "room": room, "openings": openings, "items": items}
    try:
        geo.build_room(config, style["wall"], item_color=style["furniture"])  # the model must build before it is saved
    except (geo.RoomError, ValueError) as e:  # pragma: no cover - inputs were validated step by step
        raise ValidationError({"detail": str(e)})
    if flow.design_id:
        d = flow.design
        d.config, d.room_image = config, photo
        d.save()
    else:
        flow.design = Design.objects.create(owner=flow.owner, kind=Design.Kind.INTERIOR, name=f"Room: {a['goal']}", config=config, room_image=photo)
    return warnings, bool(previous and previous["items"])


@transaction.atomic
def back(flow: RoomFlow) -> dict:
    _require_active(flow)
    try:
        new = flow_mod.back(_state(flow))
    except flow_mod.FlowError as e:
        raise _conflict("cannot_go_back", str(e))
    _store(flow, new)
    return view(flow)


def abandon(flow: RoomFlow) -> dict:
    _require_active(flow)
    flow.status = RoomFlow.Status.ABANDONED
    flow.save(update_fields=["status", "updated_at"])
    return view(flow)


def attach_photo(flow: RoomFlow, f) -> dict:
    """Bot upload: validated like every other upload, stored in the gallery as a room photo, then answered as the photo step."""
    from apps.core.validators import validate_image
    _require_active(flow)
    if flow.step != "photo":
        raise _conflict("step_mismatch", f"A photo can only be added at the photo step (current step: {flow.step}).", expected=flow.step)
    try:
        validate_image(f)
    except DjangoValidationError as e:
        raise ValidationError({"file": e.messages})
    enforce_storage_limit(flow.owner, f.size)
    w, h = Image.open(f).size
    f.seek(0)
    img = GalleryImage.objects.create(owner=flow.owner, image=f, name=(f.name.rsplit(".", 1)[0] or "Room photo")[:160], source=GalleryImage.Source.ROOM,
                                      width=w, height=h, size_bytes=f.size)
    return answer(flow, "photo", {"image_id": img.id})


# ------------------------------------------------------------------------------------------------ 3D model and items

def model(flow: RoomFlow) -> dict:
    cfg = _config(flow)
    style = next(s for s in STYLES if s["id"] == cfg["style"])
    built = geo.build_room(cfg, style["wall"], item_color=style["furniture"])
    return {"rev": cfg["rev"], "goal": cfg["goal"], "style": cfg["style"], "room": cfg["room"], "openings": cfg["openings"], "items": cfg["items"],
            **built, "requires_professional_review": True, "disclaimer": DISCLAIMER}


def _locked_config(flow: RoomFlow, rev: int) -> tuple[Design, dict]:
    _require_active(flow)
    _config(flow)  # 409 when the room has not been generated yet
    if flow.step != "furnish":
        raise _conflict("not_furnishing", f"Furniture can be changed at the furnish step (current step: {flow.step}).", expected="furnish")
    design = Design.objects.select_for_update().get(pk=flow.design_id)
    cfg = design.config
    if rev != cfg["rev"]:
        raise _conflict("rev_conflict", "The room was changed elsewhere. Reload it and try again.", current_rev=cfg["rev"])
    return design, cfg


def _commit(design: Design, flow: RoomFlow, cfg: dict) -> int:
    cfg["rev"] += 1
    design.config = cfg
    design.save()
    flow.save(update_fields=["updated_at"])
    return cfg["rev"]


def _fail(e: geo.RoomError):
    raise ValidationError(e.errors)


@transaction.atomic
def add_item(flow: RoomFlow, data: dict, rev: int) -> dict:
    design, cfg = _locked_config(flow, rev)
    items = cfg["items"]
    if len(items) >= geo.MAX_ITEMS:
        raise ValidationError({"items": f"At most {geo.MAX_ITEMS} items."})
    data = {k: v for k, v in data.items() if k in ITEM_FIELDS}
    if data.get("template"):
        t = next((t for t in catalog_context().templates if t["slug"] == data["template"]), None)
        if t is None:
            raise ValidationError({"template": "Unknown furniture template."})
        d = t["defaults"]
        base = {"name": t["name"], "width": d["width"], "depth": d["depth"], "height": d["height"], "shelves": d.get("shelves", 0),
                "doors": d.get("doors", 0), "drawers": d.get("drawers", 0), "thickness": d.get("thickness", 18)}
        data = {**base, **data}
    missing = {k: "Required." for k in ("width", "depth", "height") if k not in data}
    if missing:
        raise ValidationError(missing)
    style = next(s for s in STYLES if s["id"] == cfg["style"])
    data.setdefault("color", style["furniture"])
    if "rot" in data and data["rot"] not in geo.ROTATIONS:
        raise ValidationError({"rot": "must be 0, 90, 180 or 270"})
    try:
        if "x" in data and "z" in data:
            item, warnings = geo.validate_item({**data, "rot": data.get("rot", 0)}, cfg["room"], items, cfg["openings"])
        else:
            # Check the item itself first, so a bad size or height is reported as such instead of "no free spot".
            try:
                geo.validate_item({**data, "x": 0, "z": 0, "rot": 0}, cfg["room"], [], [])
            except geo.RoomError as e:
                own = {k: v for k, v in e.errors.items() if k != "position"}
                if own:
                    raise geo.RoomError(own)
                raise ValidationError({"position": "The item is larger than the room."})
            placed = geo.auto_place(data, cfg["room"], items, cfg["openings"])
            if placed is None:
                raise ValidationError({"position": "There is no free spot in the room for this item."})
            item, warnings = placed
    except geo.RoomError as e:
        _fail(e)
    items.append(item)
    new_rev = _commit(design, flow, cfg)
    track(flow.owner, "room_item_added", template=item.get("template", ""))
    return {"rev": new_rev, "item": item, "items": items, "warnings": geo.layout_warnings(cfg["room"], cfg["openings"], items) or warnings}


def _find(items: list, item_id: str) -> int:
    for i, it in enumerate(items):
        if it["id"] == item_id:
            return i
    raise Http404


@transaction.atomic
def update_item(flow: RoomFlow, item_id: str, changes: dict, rev: int) -> dict:
    design, cfg = _locked_config(flow, rev)
    items = cfg["items"]
    idx = _find(items, item_id)
    merged = {**items[idx], **{k: v for k, v in changes.items() if k in ITEM_FIELDS}}
    try:
        item, _ = geo.validate_item(merged, cfg["room"], [o for i, o in enumerate(items) if i != idx], cfg["openings"])
    except geo.RoomError as e:
        _fail(e)
    items[idx] = item
    new_rev = _commit(design, flow, cfg)
    return {"rev": new_rev, "item": item, "items": items, "warnings": geo.layout_warnings(cfg["room"], cfg["openings"], items)}


@transaction.atomic
def delete_item(flow: RoomFlow, item_id: str, rev: int) -> dict:
    design, cfg = _locked_config(flow, rev)
    idx = _find(cfg["items"], item_id)
    cfg["items"].pop(idx)
    new_rev = _commit(design, flow, cfg)
    return {"rev": new_rev, "items": cfg["items"], "warnings": geo.layout_warnings(cfg["room"], cfg["openings"], cfg["items"])}
