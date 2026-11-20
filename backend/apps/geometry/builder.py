"""Parametric 3D geometry from calculation parameters. Pure Python.

Axes: x = width, y = height (up), z = depth (z=0 back, z=depth front). Units: mm.
`boxes` are axis-aligned and are rendered directly by the React Three Fiber viewer
and exported to GLB / glTF / OBJ by `exporters.py`.
"""
from __future__ import annotations

from apps.calculations import engine
from apps.calculations.engine import CabinetInput

KIND_COLORS = {"carcass": "#c9a27a", "shelf": "#c9a27a", "door": "#b98f63", "drawer": "#b98f63", "back": "#8a7560", "handle": "#9ca3af"}


def _box(name, kind, x, y, z, sx, sy, sz, color=None):
    return {"name": name, "kind": kind, "x": round(x, 2), "y": round(y, 2), "z": round(z, 2),
            "sx": round(sx, 2), "sy": round(sy, 2), "sz": round(sz, 2), "color": color or KIND_COLORS[kind]}


def build_cabinet(data: dict | CabinetInput, color: str | None = None) -> dict:
    inp = data if isinstance(data, CabinetInput) else CabinetInput.from_dict(data)
    warnings = engine.validate(inp)
    W, H, D, t = inp.width, inp.height, inp.depth, inp.thickness
    lay = engine.layout(inp)
    boxes = [
        _box("Left side", "carcass", 0, 0, 0, t, H, D, color),
        _box("Right side", "carcass", W - t, 0, 0, t, H, D, color),
        _box("Bottom", "carcass", t, 0, 0, W - 2 * t, t, D, color),
        _box("Top", "carcass", t, H - t, 0, W - 2 * t, t, D, color),
        _box("Back", "back", 2, 2, -inp.back_thickness, W - 4, H - 4, inp.back_thickness),
    ]
    slot = lay["slot_h"]
    # horizontal dividers: boundaries between slots (i = 1 .. levels-1); drawers sit in the first `drawers` slots
    for i in range(1, lay["levels"]):
        if i <= inp.drawers:
            continue  # boundary above a drawer is the drawer front gap, not a board
        y = t + slot * i - t / 2
        boxes.append(_box(f"Shelf {i - inp.drawers}", "shelf", t, y, 0, W - 2 * t, t, D - engine.SHELF_SETBACK, color))
    fh = lay["drawer_front_h"]
    for d in range(inp.drawers):
        y = t + d * (fh + engine.DRAWER_FRONT_GAP) + engine.DRAWER_FRONT_GAP / 2
        boxes.append(_box(f"Drawer front {d + 1}", "drawer", t + 2, y, D, lay["inner_w"] - 4, fh, t, color))
        boxes.append(_box(f"Drawer handle {d + 1}", "handle", W / 2 - 60, y + fh - 25, D + t, 120, 8, 12))
    if inp.doors:
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
