"""Adapter from the old interior designer (Design.kind="interior", free-form config) to the room designer (room.v1).

The old designer stored ONE cabinet placed against ONE wall: {room, style, template, input, color, wallColor, roomW, roomL, roomH, wall, align, notes}.
This module is pure (no database): it turns such a config into the new config and the conversation answers. Nothing is guessed silently:
- a field the new designer cannot represent exactly is reported in `notes`;
- a cabinet that does not fit becomes a `not_placed` warning (the room itself is still imported);
- a room size outside the new limits is an error that names the old field (`roomW` ...), because the room cannot be built without it.
The original config is kept verbatim under `legacy`, so nothing the old designer stored is lost.
"""
from __future__ import annotations

from apps.conversations import flow
from apps.designs.presets import STYLES
from apps.geometry import room as geo

SCHEMA = "room.v1"
FLOOR_COLOR = "#d6c9b4"
OLD_FIELD = {"width": "roomW", "length": "roomL", "height": "roomH"}
DEFAULT_INPUT = {"width": 1800, "height": 450, "depth": 400, "thickness": 18, "shelves": 1, "doors": 2, "drawers": 0}
DEFAULTS = {"room": "living", "style": "modern", "template": "", "color": "#e5e7eb", "wallColor": "#cbd5e1", "roomW": 4200, "roomL": 5000, "roomH": 2700,
            "wall": "north", "align": "center", "notes": ""}


class LegacyError(Exception):
    """The old design cannot be converted. `errors` maps the OLD field name to the reason."""

    def __init__(self, errors: dict[str, str]):
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))
        self.errors = errors


def is_room_design(config: dict) -> bool:
    return isinstance(config, dict) and config.get("schema") == SCHEMA


def _hex(v, fallback: str) -> str:
    return v if isinstance(v, str) and geo.HEX.match(v) else fallback


def convert(config: dict, templates: list[dict], photo_id: int | None = None) -> dict:
    """Returns {"answers", "config", "notes"} for a legacy interior config. Raises LegacyError for a room that cannot be built."""
    if not isinstance(config, dict):
        raise LegacyError({"config": "must be an object"})
    if is_room_design(config):
        raise LegacyError({"config": "this design is already a room-designer design"})
    c = {**DEFAULTS, **{k: v for k, v in config.items() if k in DEFAULTS}}
    notes: list[str] = []

    try:
        size = geo.validate_room({"width": c["roomW"], "length": c["roomL"], "height": c["roomH"]})
    except geo.RoomError as e:
        raise LegacyError({OLD_FIELD[k]: v for k, v in e.errors.items()})

    style = next((s for s in STYLES if s["id"] == c["style"]), None)
    if style is None:
        style = STYLES[0]
        notes.append(f"Unknown style {c['style']!r}; used {style['id']}.")
    wall_color, item_color = _hex(c["wallColor"], style["wall"]), _hex(c["color"], style["furniture"])

    by_slug = {t["slug"]: t for t in templates}
    slug = c["template"] if isinstance(c["template"], str) and c["template"] in by_slug else ""
    if c["template"] and not slug:
        notes.append(f"Furniture template {c['template']!r} no longer exists; the cabinet keeps its own sizes.")
    goal = c["room"] if c["room"] in flow.GOAL_IDS else "other"
    if goal != c["room"]:
        notes.append(f"Unknown room type {c['room']!r}; used 'other'.")
    if slug and goal != "other" and slug not in {t["slug"] for t in flow.FlowContext(templates=templates).allowed_templates(goal)}:
        goal = "other"                                    # keep the cabinet selectable in the new designer

    items: list[dict] = []
    not_placed: list[dict] = []
    if isinstance(config.get("input"), dict):
        items, not_placed = _place(c, config["input"], size, slug, by_slug, item_color)
    elif "input" in config:
        notes.append("Furniture sizes were not a valid object; no cabinet was placed.")

    answers = {"goal": goal, "photo": {"image_id": photo_id} if photo_id else {"skipped": True},
               "elements": {"doors": 0, "windows": 0, "furniture": [slug] if slug else []}, "size": size, "openings": [], "style": style["id"]}
    new = {"schema": SCHEMA, "goal": goal, "style": style["id"], "room": size, "openings": [], "items": items, "not_placed": not_placed,
           "colors": {"wall": wall_color, "floor": FLOOR_COLOR, "item": item_color}, "notes": c["notes"] if isinstance(c["notes"], str) else "",
           "legacy": config, "import_notes": notes}
    return {"answers": answers, "config": new, "notes": notes}


def _place(c: dict, inp: dict, room: dict, slug: str, by_slug: dict, color: str) -> tuple[list[dict], list[dict]]:
    t = by_slug.get(slug)
    name = t["name"] if t else "Furniture"
    miss = lambda why: ([], [{"code": "not_placed", "item": slug or "legacy", "message": f"{name} could not be placed: {why}"}])  # noqa: E731
    base = {**DEFAULT_INPUT, **{k: v for k, v in inp.items() if k in DEFAULT_INPUT}}
    try:
        w, d = float(base["width"]), float(base["depth"])
    except (TypeError, ValueError):
        return miss("width and depth must be numbers")
    wall = c["wall"] if c["wall"] in geo.WALLS else "north"
    horiz = wall in ("north", "south")
    fw, fh = (w, d) if horiz else (d, w)                  # footprint on the plan, as the old plan drew it
    span = (room["width"] - fw) if horiz else (room["length"] - fh)
    if span < 0:
        return miss(f"it is wider than the {wall} wall")
    off = 0 if c["align"] == "start" else span if c["align"] == "end" else span / 2
    x = 0 if wall == "west" else room["width"] - fw if wall == "east" else off
    z = 0 if wall == "north" else room["length"] - fh if wall == "south" else off
    item = {"template": slug, "name": name, "x": x, "z": z, "rot": geo.WALL_ROT[wall], "color": color, **base}
    try:
        placed, _ = geo.validate_item(item, room, [], [])
    except geo.RoomError as e:
        return miss(str(e))
    return [placed], []
