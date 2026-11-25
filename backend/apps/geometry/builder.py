"""Parametric 3D geometry from calculation parameters. Pure Python.

Axes: x = width, y = height (up), z = depth (z=0 back, z=depth front). Units: mm.
`boxes` are axis-aligned and are rendered directly by the React Three Fiber viewer
and exported to GLB / glTF / OBJ by `exporters.py`.
"""
from __future__ import annotations

from apps.calculations import engine
from apps.calculations.engine import CabinetInput

PLINTH_SETBACK = 60  # 3D model only: the plinth board is set back from the cabinet front
KIND_COLORS = {"carcass": "#c9a27a", "shelf": "#c9a27a", "door": "#b98f63", "drawer": "#b98f63", "back": "#8a7560", "handle": "#9ca3af"}


def _box(name, kind, x, y, z, sx, sy, sz, color=None):
    return {"name": name, "kind": kind, "x": round(x, 2), "y": round(y, 2), "z": round(z, 2),
            "sx": round(sx, 2), "sy": round(sy, 2), "sz": round(sz, 2), "color": color or KIND_COLORS[kind]}


def build_cabinet(data: dict | CabinetInput, color: str | None = None) -> dict:
    inp = data if isinstance(data, CabinetInput) else CabinetInput.from_dict(data)
    warnings = engine.validate(inp)
    W, H, D, t = inp.width, inp.height, inp.depth, inp.thickness
    lay = engine.layout(inp)
    by, bh = lay["base_y"], lay["body_h"]   # carcass underside above the floor, carcass height
    kind = inp.cabinet_type
    boxes = [
        _box("Left side", "carcass", 0, by, 0, t, bh, D, color),
        _box("Right side", "carcass", W - t, by, 0, t, bh, D, color),
        _box("Bottom", "carcass", t, by, 0, W - 2 * t, t, D, color),
    ]
    if kind == "kitchen_base":
        rw = inp.rail_width
        boxes.append(_box("Front top rail", "carcass", t, H - t, D - rw, W - 2 * t, t, rw, color))
        boxes.append(_box("Rear top rail", "carcass", t, H - t, 0, W - 2 * t, t, rw, color))
        boxes.append(_box("Plinth", "carcass", 0, 0, D - PLINTH_SETBACK - t, W, by, t, color))
    else:
        boxes.append(_box("Top", "carcass", t, H - t, 0, W - 2 * t, t, D, color))
    boxes.append(_box("Back", "back", 2, by + 2, -inp.back_thickness, W - 4, bh - 4, inp.back_thickness))
    if kind == "kitchen_wall":
        boxes.append(_box("Hanging rail", "carcass", t, H - t - inp.rail_width, 0, W - 2 * t, inp.rail_width, t, color))
    slot = lay["slot_h"]
    # horizontal dividers: boundaries between slots (i = 1 .. levels-1); drawers sit in the first `drawers` slots
    for i in range(1, lay["levels"]):
        if i <= inp.drawers:
            continue  # boundary above a drawer is the drawer front gap, not a board
        y = by + t + slot * i - t / 2
        boxes.append(_box(f"Shelf {i - inp.drawers}", "shelf", t, y, 0, W - 2 * t, t, D - engine.SHELF_SETBACK, color))
    fh = lay["drawer_front_h"]
    for d in range(inp.drawers):
        y = by + t + d * (fh + engine.DRAWER_FRONT_GAP) + engine.DRAWER_FRONT_GAP / 2
        boxes.append(_box(f"Drawer front {d + 1}", "drawer", t + 2, y, D, lay["inner_w"] - 4, fh, t, color))
        boxes.append(_box(f"Drawer handle {d + 1}", "handle", W / 2 - 60, y + fh - 25, D + t, 120, 8, 12))
    if inp.doors and kind == "sliding_wardrobe":
        dw, pitch = lay["door_w"], t + engine.SLIDING_LANE_GAP
        # neighbouring panels alternate between two lanes; lane 0 is the front one
        for k in range(inp.doors):
            lane = k % 2
            x = t + k * (dw - inp.sliding_overlap)
            z = D - engine.SLIDING_FRONT_SETBACK - t - lane * pitch
            boxes.append(_box(f"Sliding door {k + 1}", "door", x, lay["door_y"], z, dw, lay["door_h"], t, color))
            hx = x + dw - 22 if k % 2 == 0 else x + 10
            boxes.append(_box(f"Door handle {k + 1}", "handle", hx, lay["door_y"] + lay["door_h"] / 2 - 60, z, 12, 120, t))
        boxes.append(_box("Top track", "handle", t, H - t - inp.track_top, D - engine.SLIDING_FRONT_SETBACK - t - pitch, lay["inner_w"], inp.track_top, 2 * t + engine.SLIDING_LANE_GAP))
        boxes.append(_box("Bottom track", "handle", t, by + t, D - engine.SLIDING_FRONT_SETBACK - t - pitch, lay["inner_w"], inp.track_bottom, 2 * t + engine.SLIDING_LANE_GAP))
    elif inp.doors:
        dw = lay["door_w"]
        for k in range(inp.doors):
            x = engine.DOOR_EDGE_GAP + k * (dw + engine.DOOR_GAP)
            boxes.append(_box(f"Door {k + 1}", "door", x, lay["door_y"], D, dw, lay["door_h"], t, color))
            hx = x + dw - 22 if k % 2 == 0 else x + 14
            boxes.append(_box(f"Door handle {k + 1}", "handle", hx, lay["door_y"] + lay["door_h"] / 2 - 60, D + t, 8, 120, 12))
    return {
        "dimensions": {"width": W, "height": H, "depth": D, "thickness": t},
        "boxes": boxes,
        "bounds": {"min": [0, 0, -inp.back_thickness], "max": [W, H, D + t + 12]},
        "warnings": warnings,
        "requires_professional_review": True,
    }
