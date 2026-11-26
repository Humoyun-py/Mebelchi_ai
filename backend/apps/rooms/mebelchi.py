""".mebelchi project files: a JSON document that carries one room design between Mebelchi AI web and mobile (and between accounts).

What it is: a portable, versioned, integrity-checked project file (room, openings, furniture with positions, colours, camera, settings, and
references to catalogue models by id). What it is NOT: copy protection. Anyone who has the file can read it; the SHA-256 only detects
accidental corruption or hand edits, it is not a signature and does not authenticate the author. Imported data is validated exactly like data
typed into the designer, so a hand-written file can never put an impossible room into the system.

Pure module (no database): `build()` makes the document, `parse()` validates one and returns the pieces the service needs.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from apps.conversations import flow
from apps.designs.presets import STYLES
from apps.geometry import room as geo

FORMAT, VERSION, KIND = "mebelchi", 1, "room"
MAX_BYTES = 1024 * 1024
EXTENSION = ".mebelchi"
FLOOR_MATERIALS = ("wood", "laminate", "tile", "concrete", "carpet")
NOTICE = "Mebelchi AI project file. It is a portable format, not copy protection."


class MebelchiError(ValueError):
    """The file cannot be imported. `errors` maps a path in the file to the reason."""

    def __init__(self, errors: dict[str, str]):
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))
        self.errors = errors


def _digest(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def build(name: str, config: dict) -> dict:
    """The project document for a room.v1 config."""
    items = config.get("items", [])
    body = {"format": FORMAT, "version": VERSION, "kind": KIND, "name": name, "notice": NOTICE,
            "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "room": config["room"], "openings": config.get("openings", []), "goal": config.get("goal"), "style": config.get("style"),
            "colors": config.get("colors", {}), "floor_material": config.get("floor_material"),
            "furniture": items,
            "models": sorted({i["template"] for i in items if i.get("template")}),     # catalogue ids; the geometry is rebuilt from the sizes
            "camera": config.get("camera"), "light": config.get("light"), "settings": {"notes": config.get("notes", "")}}
    return {**body, "checksum": {"alg": "sha256", "value": _digest(body)}}


def dumps(doc: dict) -> bytes:
    return json.dumps(doc, indent=2, ensure_ascii=False).encode()


def _num_list(v, n, path, errors):
    if v is None:
        return None
    if not (isinstance(v, list) and len(v) == n and all(geo._is_num(x) and abs(x) <= 1e6 for x in v)):
        errors[path] = f"must be {n} numbers"
        return None
    return [float(x) for x in v]


def validate_camera(cam, errors: dict, path="camera"):
    if cam is None:
        return None
    if not isinstance(cam, dict):
        errors[path] = "must be an object"
        return None
    out = {"position": _num_list(cam.get("position"), 3, f"{path}.position", errors), "target": _num_list(cam.get("target"), 3, f"{path}.target", errors)}
    fov = cam.get("fov", 50)
    if not geo._is_num(fov) or not 10 <= fov <= 120:
        errors[f"{path}.fov"] = "must be a number between 10 and 120"
    else:
        out["fov"] = float(fov)
    return out


def validate_light(light, errors: dict, path="light"):
    if light is None:
        return None
    if not isinstance(light, dict):
        errors[path] = "must be an object"
        return None
    inten = light.get("intensity", 1)
    if not geo._is_num(inten) or not 0.2 <= inten <= 2:
        errors[f"{path}.intensity"] = "must be a number between 0.2 and 2"
    warm = light.get("warm", False)
    if not isinstance(warm, bool):
        errors[f"{path}.warm"] = "must be true or false"
    return {"intensity": float(inten) if geo._is_num(inten) else 1.0, "warm": warm if isinstance(warm, bool) else False}


def validate_colors(c, errors: dict, path="colors"):
    if c is None:
        return None
    if not isinstance(c, dict) or set(c) - {"wall", "floor", "item"}:
        errors[path] = "must be an object with wall, floor and item colours"
        return None
    out = {}
    for k, v in c.items():
        if not (isinstance(v, str) and geo.HEX.match(v)):
            errors[f"{path}.{k}"] = "must be a hex colour like #c9a27a"
        else:
            out[k] = v
    return out


def parse(raw: bytes | str | dict) -> dict:
    """Validates a project file; returns {name, config} where config is a complete room.v1 document. Raises MebelchiError."""
    if isinstance(raw, (bytes, str)):
        if len(raw) > MAX_BYTES:
            raise MebelchiError({"file": f"too large (max {MAX_BYTES // 1024} KB)"})
        try:
            doc = json.loads(raw)
        except ValueError:
            raise MebelchiError({"file": "this is not a .mebelchi project file (JSON could not be read)"})
    else:
        doc = raw
    if not isinstance(doc, dict) or doc.get("format") != FORMAT:
        raise MebelchiError({"format": "this is not a .mebelchi project file"})
    if doc.get("version") != VERSION:
        raise MebelchiError({"version": f"unsupported version {doc.get('version')!r}; this server reads version {VERSION}"})
    if doc.get("kind") != KIND:
        raise MebelchiError({"kind": f"only '{KIND}' projects can be imported"})
    cs = doc.get("checksum")
    body = {k: v for k, v in doc.items() if k != "checksum"}
    if not (isinstance(cs, dict) and cs.get("alg") == "sha256" and cs.get("value") == _digest(body)):
        raise MebelchiError({"checksum": "the file is damaged or was edited after it was exported"})

    errors: dict[str, str] = {}
    name = doc.get("name")
    if not isinstance(name, str) or not name.strip():
        errors["name"] = "is required"
    try:
        room = geo.validate_room(doc.get("room"))
    except geo.RoomError as e:
        raise MebelchiError({f"room.{k}": v for k, v in e.errors.items()})
    try:
        openings = geo.validate_openings(doc.get("openings", []), room)
    except geo.RoomError as e:
        raise MebelchiError(e.errors)
    style = doc.get("style")
    if style not in flow.STYLE_IDS:
        errors["style"] = f"must be one of: {', '.join(flow.STYLE_IDS)}"
    goal = doc.get("goal")
    if goal not in flow.GOAL_IDS:
        errors["goal"] = f"must be one of: {', '.join(flow.GOAL_IDS)}"
    colors = validate_colors(doc.get("colors"), errors)
    fm = doc.get("floor_material")
    if fm is not None and fm not in FLOOR_MATERIALS:
        errors["floor_material"] = f"must be one of: {', '.join(FLOOR_MATERIALS)}"
    camera, light = validate_camera(doc.get("camera"), errors), validate_light(doc.get("light"), errors)
    settings = doc.get("settings") or {}
    notes = settings.get("notes", "") if isinstance(settings, dict) else ""
    if not isinstance(notes, str) or len(notes) > 1000:
        errors["settings.notes"] = "must be text up to 1000 characters"
    furniture = doc.get("furniture", [])
    if not isinstance(furniture, list) or len(furniture) > geo.MAX_ITEMS:
        errors["furniture"] = f"must be a list of at most {geo.MAX_ITEMS} items"
    if errors:
        raise MebelchiError(errors)
    items: list[dict] = []
    for n, raw_item in enumerate(furniture):
        try:
            item, _ = geo.validate_item(raw_item, room, items, openings)
        except geo.RoomError as e:
            raise MebelchiError({f"furniture.{n}.{k}": v for k, v in e.errors.items()})
        items.append(item)
    style_def = next(s for s in STYLES if s["id"] == style)
    config = {"schema": "room.v1", "goal": goal, "style": style, "room": room, "openings": openings, "items": items, "not_placed": [],
              "colors": {"wall": style_def["wall"], "floor": "#d6c9b4", "item": style_def["furniture"], **(colors or {})}, "notes": notes}
    for k, v in (("floor_material", fm), ("camera", camera), ("light", light)):
        if v is not None:
            config[k] = v
    return {"name": name.strip()[:160], "config": config}
