"""Parametric 3D room geometry. Pure Python, no Django, no external AI.

Units are millimetres. Axes match apps/geometry/builder.py: x = width (west -> east), y = up,
z = length (north z=0 -> south z=L). The interior volume is x in [0, W], z in [0, L], y in [0, H];
walls are built outside it (thickness WALL_T).

Walls: north (z=0) and south (z=L) run along x, west (x=0) and east (x=W) run along z.
An opening's `offset` is measured from the wall's start: the west end of north/south walls,
the north end of west/east walls.

Furniture items are cabinets (apps/calculations/engine.py validates their size and structure). `x`,`z` is the
minimum corner of the item's footprint AFTER rotation. `rot` is 0, 90, 180 or 270 degrees; rot 0 faces +z (into a
room from the north wall), 90 faces +x, 180 faces -z, 270 faces -x. Every box stays axis-aligned, so the viewer and
the GLB/glTF/OBJ exporters work unchanged.

Layouts are visual planning aids, not verified for manufacture.
"""
from __future__ import annotations

import re
import uuid
from math import isfinite

from apps.calculations import engine
from apps.geometry.builder import build_cabinet

LIMITS = {"width": (1000, 15000), "length": (1000, 15000), "height": (2000, 4500)}
DOOR_LIMITS = {"width": (600, 1200), "height": (1800, 2400)}
WINDOW_LIMITS = {"width": (300, 3000), "height": (300, 2400), "sill": (0, 1500)}
MAX_DOORS, MAX_WINDOWS, MAX_ITEMS = 2, 4, 60
EDGE_MARGIN = 100       # opening to wall end
OPENING_GAP = 100       # opening to opening on the same wall
CEILING_MARGIN = 100    # sill + height <= room height - margin
WALL_T, SLAB_T = 100, 50
DOOR_ZONE = 800         # free area in front of a door; blocking it is a warning, not an error
WALLS = ("north", "east", "south", "west")
ROTATIONS = (0, 90, 180, 270)
WALL_ROT = {"north": 0, "east": 270, "south": 180, "west": 90}  # rotation that makes an item face into the room
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class RoomError(ValueError):
    """Validation failure. `errors` maps field name -> message."""

    def __init__(self, errors: dict[str, str]):
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))
        self.errors = errors


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and isfinite(v)


def _clean(v):
    return int(v) if float(v).is_integer() else round(float(v), 1)


def _range(errors: dict, key: str, v, lo, hi, label: str | None = None):
    if not _is_num(v):
        errors[key] = "must be a number"
        return None
    if v < lo or v > hi:
        errors[key] = f"must be between {lo} and {hi} mm" if label is None else f"{label} must be between {lo} and {hi}"
        return None
    return _clean(v)


# ------------------------------------------------------------------------------------------------ room and openings

def validate_room(room: dict) -> dict:
    if not isinstance(room, dict):
        raise RoomError({"room": "must be an object"})
    errors: dict[str, str] = {}
    out = {k: _range(errors, k, room.get(k), *LIMITS[k]) for k in LIMITS}
    if errors:
        raise RoomError(errors)
    return out  # type: ignore[return-value]


def wall_length(room: dict, wall: str) -> float:
    return room["width"] if wall in ("north", "south") else room["length"]


def validate_opening(opening: dict, room: dict) -> dict:
    """Returns a normalized opening. Does not check overlaps with other openings (see validate_openings)."""
    if not isinstance(opening, dict):
        raise RoomError({"opening": "must be an object"})
    errors: dict[str, str] = {}
    kind = opening.get("type")
    if kind not in ("door", "window"):
        errors["type"] = "must be door or window"
    wall = opening.get("wall")
    if wall not in WALLS:
        errors["wall"] = "must be north, east, south or west"
    if errors:
        raise RoomError(errors)
    limits = DOOR_LIMITS if kind == "door" else WINDOW_LIMITS
    width = _range(errors, "width", opening.get("width"), *limits["width"])
    height = _range(errors, "height", opening.get("height"), *limits["height"])
    if kind == "door":
        sill = opening.get("sill", 0)
        if not _is_num(sill) or sill != 0:
            errors["sill"] = "a door starts at the floor (sill must be 0)"
            sill = None
        else:
            sill = 0
    else:
        sill = _range(errors, "sill", opening.get("sill", 0), *WINDOW_LIMITS["sill"])
    offset = opening.get("offset")
    if not _is_num(offset):
        errors["offset"] = "must be a number"
        offset = None
    if errors:
        raise RoomError(errors)
    wl = wall_length(room, wall)
    if offset < EDGE_MARGIN:
        errors["offset"] = f"must be at least {EDGE_MARGIN} mm from the wall end"
    elif offset + width > wl - EDGE_MARGIN:
        errors["offset"] = f"opening does not fit: it must end at least {EDGE_MARGIN} mm before the wall end ({wl} mm wall)"
    if sill + height > room["height"] - CEILING_MARGIN:
        errors["height"] = f"top of the opening must be at least {CEILING_MARGIN} mm below the ceiling ({room['height']} mm)"
    if errors:
        raise RoomError(errors)
    return {"id": str(opening.get("id") or new_id()), "type": kind, "wall": wall, "offset": _clean(offset),
            "width": width, "height": height, "sill": sill}


def validate_openings(openings, room: dict) -> list[dict]:
    if not isinstance(openings, list):
        raise RoomError({"openings": "must be a list"})
    errors: dict[str, str] = {}
    out: list[dict] = []
    for i, o in enumerate(openings):
        try:
            out.append(validate_opening(o, room))
        except RoomError as e:
            for k, v in e.errors.items():
                errors[f"openings.{i}.{k}"] = v
    if errors:
        raise RoomError(errors)
    if sum(o["type"] == "door" for o in out) > MAX_DOORS:
        errors["openings"] = f"at most {MAX_DOORS} doors"
    if sum(o["type"] == "window" for o in out) > MAX_WINDOWS:
        errors["openings"] = f"at most {MAX_WINDOWS} windows"
    for wall in WALLS:
        on = sorted((o for o in out if o["wall"] == wall), key=lambda o: o["offset"])
        for a, b in zip(on, on[1:]):
            if b["offset"] - (a["offset"] + a["width"]) < OPENING_GAP:
                errors["openings"] = f"openings on the {wall} wall overlap or are closer than {OPENING_GAP} mm"
    if errors:
        raise RoomError(errors)
    return out


# ------------------------------------------------------------------------------------------------ furniture

def footprint(item: dict) -> tuple[float, float, float, float]:
    """(x0, z0, x1, z1) of the item's footprint after rotation."""
    fw, fd = (item["width"], item["depth"]) if item["rot"] in (0, 180) else (item["depth"], item["width"])
    return item["x"], item["z"], item["x"] + fw, item["z"] + fd


def _overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def door_zones(room: dict, openings) -> list[tuple[float, float, float, float]]:
    zones = []
    for o in openings:
        if o["type"] != "door":
            continue
        a0, a1 = o["offset"], o["offset"] + o["width"]
        W, L = room["width"], room["length"]
        zones.append({"north": (a0, 0, a1, DOOR_ZONE), "south": (a0, L - DOOR_ZONE, a1, L),
                      "west": (0, a0, DOOR_ZONE, a1), "east": (W - DOOR_ZONE, a0, W, a1)}[o["wall"]])
    return zones


def validate_item(item: dict, room: dict, others=(), openings=()) -> tuple[dict, list[dict]]:
    """Returns (normalized item, warnings). `others` are the other items in the room (not including this one)."""
    if not isinstance(item, dict):
        raise RoomError({"item": "must be an object"})
    errors: dict[str, str] = {}
    for k in ("x", "z", "width", "depth", "height"):
        if not _is_num(item.get(k)):
            errors[k] = "must be a number"
    rot = item.get("rot", 0)
    if isinstance(rot, bool) or not _is_num(rot) or rot not in ROTATIONS:
        errors["rot"] = "must be 0, 90, 180 or 270"
    counts = {}
    for k in ("shelves", "doors", "drawers"):
        v = item.get(k, 0)
        if isinstance(v, bool) or not isinstance(v, int):
            errors[k] = "must be a whole number"
        counts[k] = v
    color = item.get("color")
    if color not in (None, "") and not (isinstance(color, str) and HEX.match(color)):  # "" means "use the style color"
        errors["color"] = "must be a hex color like #c9a27a"
    for k, n in (("name", 80), ("template", 64)):
        if item.get(k) is not None and (not isinstance(item[k], str) or len(item[k]) > n):
            errors[k] = f"must be text up to {n} characters"
    thickness = item.get("thickness", 18)
    if errors:
        raise RoomError(errors)
    # size and structure come from the cabinet engine, so limits and impossible-geometry rules stay in one place
    try:
        engine.validate(engine.CabinetInput(width=item["width"], height=item["height"], depth=item["depth"], thickness=thickness, **counts))
    except engine.EngineValidationError as e:
        raise RoomError(dict(e.errors))
    if item["height"] > room["height"]:
        raise RoomError({"height": f"taller than the room ({room['height']} mm)"})
    out = {"id": str(item.get("id") or new_id()), "template": item.get("template") or "", "name": (item.get("name") or "").strip(),
           "x": _clean(item["x"]), "z": _clean(item["z"]), "rot": int(rot), "width": _clean(item["width"]), "depth": _clean(item["depth"]),
           "height": _clean(item["height"]), **counts, "color": color or ""}
    if thickness != 18:
        out["thickness"] = thickness
    fp = footprint(out)
    if fp[0] < 0 or fp[1] < 0 or fp[2] > room["width"] or fp[3] > room["length"]:
        raise RoomError({"position": f"item must stay inside the room ({room['width']} x {room['length']} mm); footprint "
                                     f"{_clean(fp[2] - fp[0])} x {_clean(fp[3] - fp[1])} mm at x={out['x']}, z={out['z']}"})
    for other in others:
        if other["id"] != out["id"] and _overlap(fp, footprint(other)):
            raise RoomError({"position": f"overlaps another item ({other.get('name') or other['id']})"})
    warnings = []
    if any(_overlap(fp, z) for z in door_zones(room, openings)):
        warnings.append({"code": "door_zone", "item": out["id"], "message": f"blocks the {DOOR_ZONE} mm area in front of a door"})
    return out, warnings


def layout_warnings(room: dict, openings, items) -> list[dict]:
    zones = door_zones(room, openings)
    return [{"code": "door_zone", "item": it["id"], "message": f"blocks the {DOOR_ZONE} mm area in front of a door"}
            for it in items if any(_overlap(footprint(it), z) for z in zones)]


def _wall_rect(wall: str, a: float, item: dict, room: dict):
    """Footprint rect of `item` placed against `wall` at position `a` along it, and the rotation that faces into the room."""
    w, d = item["width"], item["depth"]
    if wall == "north":
        return (a, 0, a + w, d)
    if wall == "south":
        return (a, room["length"] - d, a + w, room["length"])
    if wall == "west":
        return (0, a, d, a + w)
    return (room["width"] - d, a, room["width"], a + w)


def auto_place(item: dict, room: dict, others=(), openings=()) -> tuple[dict, list[dict]] | None:
    """Deterministically put `item` against the first wall (longest first) with a free spot. Returns the validated item
    and its warnings, or None when it does not fit anywhere. The door zones are kept free."""
    zones = door_zones(room, openings)
    rects = [footprint(o) for o in others]
    for wall in sorted(WALLS, key=lambda w: -wall_length(room, w)):
        along_x = wall in ("north", "south")
        ends = {0}
        for r in rects + zones:
            ends.add(r[2] if along_x else r[3])
        for a in sorted(ends):
            x0, z0, x1, z1 = _wall_rect(wall, a, item, room)
            if x1 > room["width"] or z1 > room["length"]:
                continue
            rect = (x0, z0, x1, z1)
            if any(_overlap(rect, r) for r in rects + zones):
                continue
            try:
                return validate_item({**item, "x": x0, "z": z0, "rot": WALL_ROT[wall]}, room, others, openings)
            except RoomError:
                continue
    return None


def suggest_layout(templates: list[dict], room: dict, openings, color: str = "") -> tuple[list[dict], list[dict]]:
    """Place the chosen templates one after another. Returns (items, warnings); templates that do not fit are skipped
    and reported as `not_placed` warnings."""
    items: list[dict] = []
    warnings: list[dict] = []
    for t in templates[:MAX_ITEMS]:
        d = t["defaults"]
        base = {"template": t["slug"], "name": t["name"], "width": d["width"], "depth": d["depth"], "height": d["height"],
                "shelves": d.get("shelves", 0), "doors": d.get("doors", 0), "drawers": d.get("drawers", 0), "color": color or None}
        if d.get("thickness", 18) != 18:
            base["thickness"] = d["thickness"]
        placed = auto_place(base, room, items, openings)
        if placed is None:
            warnings.append({"code": "not_placed", "item": t["slug"], "message": f"{t['name']} did not fit in the room and was not placed"})
            continue
        items.append(placed[0])
        warnings.extend(placed[1])
    return items, warnings


# ------------------------------------------------------------------------------------------------ 3D model

def _box(name, kind, x, y, z, sx, sy, sz, color):
    return {"name": name, "kind": kind, "x": round(x, 2), "y": round(y, 2), "z": round(z, 2),
            "sx": round(sx, 2), "sy": round(sy, 2), "sz": round(sz, 2), "color": color}


def _wall_boxes(room: dict, openings, color: str) -> list[dict]:
    W, L, H, T = room["width"], room["length"], room["height"], WALL_T
    boxes = []
    for wall in WALLS:
        along_x = wall in ("north", "south")
        length = W if along_x else L
        pad = T if along_x else 0   # north/south walls cover the corners

        def seg(a0, a1, y0, y1, wall=wall, along_x=along_x):
            a0, a1 = a0 - (pad if a0 == 0 else 0), a1 + (pad if a1 == length else 0)
            if wall == "north":
                return _box("Wall north", "wall", a0, y0, -T, a1 - a0, y1 - y0, T, color)
            if wall == "south":
                return _box("Wall south", "wall", a0, y0, L, a1 - a0, y1 - y0, T, color)
            if wall == "west":
                return _box("Wall west", "wall", -T, y0, a0, T, y1 - y0, a1 - a0, color)
            return _box("Wall east", "wall", W, y0, a0, T, y1 - y0, a1 - a0, color)

        cursor = 0
        for o in sorted((o for o in openings if o["wall"] == wall), key=lambda o: o["offset"]):
            if o["offset"] > cursor:
                boxes.append(seg(cursor, o["offset"], 0, H))
            if o["sill"] > 0:
                boxes.append(seg(o["offset"], o["offset"] + o["width"], 0, o["sill"]))
            top = o["sill"] + o["height"]
            if top < H:
                boxes.append(seg(o["offset"], o["offset"] + o["width"], top, H))
            cursor = o["offset"] + o["width"]
        if cursor < length:
            boxes.append(seg(cursor, length, 0, H))
    return boxes


def _place_cabinet_box(b: dict, item: dict) -> dict:
    """Move a box built in the cabinet's local frame (x=width, z=depth, front at +z) into the room."""
    w, d = item["width"], item["depth"]
    bx, bz, sx, sz = b["x"], b["z"], b["sx"], b["sz"]
    rot = item["rot"]
    if rot == 0:
        wx, wz, wsx, wsz = bx, bz, sx, sz
    elif rot == 90:
        wx, wz, wsx, wsz = bz, w - bx - sx, sz, sx
    elif rot == 180:
        wx, wz, wsx, wsz = w - bx - sx, d - bz - sz, sx, sz
    else:
        wx, wz, wsx, wsz = d - bz - sz, bx, sz, sx
    return {**b, "x": round(item["x"] + wx, 2), "z": round(item["z"] + wz, 2), "sx": round(wsx, 2), "sz": round(wsz, 2), "item": item["id"]}


def build_room(config: dict, wall_color: str = "#cbd5e1", floor_color: str = "#d6c9b4", item_color: str = "#e5e7eb") -> dict:
    """config: a validated room.v1 document. Returns {"dimensions", "boxes", "warnings"}. Deterministic."""
    room, openings, items = config["room"], config.get("openings", []), config.get("items", [])
    W, L, H = room["width"], room["length"], room["height"]
    boxes = _wall_boxes(room, openings, wall_color)
    boxes.append(_box("Floor", "floor", -WALL_T, -SLAB_T, -WALL_T, W + 2 * WALL_T, SLAB_T, L + 2 * WALL_T, floor_color))
    boxes.append(_box("Ceiling", "ceiling", -WALL_T, H, -WALL_T, W + 2 * WALL_T, SLAB_T, L + 2 * WALL_T, wall_color))
    for item in items:
        cab = build_cabinet({"width": item["width"], "height": item["height"], "depth": item["depth"], "thickness": item.get("thickness", 18),
                             "shelves": item.get("shelves", 0), "doors": item.get("doors", 0), "drawers": item.get("drawers", 0)},
                            color=item.get("color") or item_color)
        boxes.extend(_place_cabinet_box(b, item) for b in cab["boxes"])
    return {"dimensions": {"width": W, "depth": L, "length": L, "height": H, "wall_thickness": WALL_T}, "boxes": boxes,
            "warnings": layout_warnings(room, openings, items)}
