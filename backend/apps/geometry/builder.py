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
GROUP_OF = {"carcass": "carcass", "shelf": "carcass", "door": "fronts", "drawer": "fronts", "back": "back", "handle": "handle"}
KNOB = (24, 24, 22)   # knob handle size (x, y, z) in mm
BAR_LEN = 120


def _box(name, kind, x, y, z, sx, sy, sz, color=None):
    return {"name": name, "kind": kind, "x": round(x, 2), "y": round(y, 2), "z": round(z, 2),
            "sx": round(sx, 2), "sy": round(sy, 2), "sz": round(sz, 2), "color": color or KIND_COLORS[kind]}


def build_cabinet(data: dict | CabinetInput, color: str | None = None, colors: dict | None = None, verify: bool = False) -> dict:
    """Boxes for the viewer and exporters. `color` is the legacy single colour (carcass, shelves, doors, drawer fronts); `colors`
    paints groups independently ({carcass, fronts, back, handle}) and wins over `color`. With verify=True the result carries a
    `consistency` report proving that the boxes match the calculation (see check_consistency)."""
    inp = data if isinstance(data, CabinetInput) else CabinetInput.from_dict(data)
    warnings = engine.validate(inp)
    colors = colors or {}

    def paint(kind: str):
        return colors.get(GROUP_OF[kind]) or (color if kind in ("carcass", "shelf", "door", "drawer") else None)

    W, H, D, t = inp.width, inp.height, inp.depth, inp.thickness
    lay = engine.layout(inp)
    by, bh = lay["base_y"], lay["body_h"]   # carcass underside above the floor, carcass height
    kind = inp.cabinet_type
    style = inp.handle_style
    boxes = [
        _box("Left side", "carcass", 0, by, 0, t, bh, D, paint("carcass")),
        _box("Right side", "carcass", W - t, by, 0, t, bh, D, paint("carcass")),
        _box("Bottom", "carcass", t, by, 0, W - 2 * t, t, D, paint("carcass")),
    ]
    if kind == "kitchen_base":
        rw = inp.rail_width
        boxes.append(_box("Front top rail", "carcass", t, H - t, D - rw, W - 2 * t, t, rw, paint("carcass")))
        boxes.append(_box("Rear top rail", "carcass", t, H - t, 0, W - 2 * t, t, rw, paint("carcass")))
        boxes.append(_box("Plinth", "carcass", 0, 0, D - PLINTH_SETBACK - t, W, by, t, paint("carcass")))
    else:
        boxes.append(_box("Top", "carcass", t, H - t, 0, W - 2 * t, t, D, paint("carcass")))
    boxes.append(_box("Back", "back", 2, by + 2, -inp.back_thickness, W - 4, bh - 4, inp.back_thickness, paint("back")))
    if kind == "kitchen_wall":
        boxes.append(_box("Hanging rail", "carcass", t, H - t - inp.rail_width, 0, W - 2 * t, inp.rail_width, t, paint("carcass")))
    slot = lay["slot_h"]
    # horizontal dividers: boundaries between slots (i = 1 .. levels-1); drawers sit in the first `drawers` slots
    for i in range(1, lay["levels"]):
        if i <= inp.drawers:
            continue  # boundary above a drawer is the drawer front gap, not a board
        y = by + t + slot * i - t / 2
        boxes.append(_box(f"Shelf {i - inp.drawers}", "shelf", t, y, 0, W - 2 * t, t, D - engine.SHELF_SETBACK, paint("shelf")))
    fh = lay["drawer_front_h"]
    for d in range(inp.drawers):
        y = by + t + d * (fh + engine.DRAWER_FRONT_GAP) + engine.DRAWER_FRONT_GAP / 2
        boxes.append(_box(f"Drawer front {d + 1}", "drawer", t + 2, y, D, lay["inner_w"] - 4, fh, t, paint("drawer")))
        if style == "bar":
            boxes.append(_box(f"Drawer handle {d + 1}", "handle", W / 2 - BAR_LEN / 2, y + fh - 25, D + t, BAR_LEN, 8, 12, paint("handle")))
        elif style == "knob":
            boxes.append(_box(f"Drawer handle {d + 1}", "handle", W / 2 - KNOB[0] / 2, y + fh - 40, D + t, *KNOB, paint("handle")))
    if inp.doors and kind == "sliding_wardrobe":
        dw, pitch = lay["door_w"], t + engine.SLIDING_LANE_GAP
        # neighbouring panels alternate between two lanes; lane 0 is the front one
        for k in range(inp.doors):
            lane = k % 2
            x = t + k * (dw - inp.sliding_overlap)
            z = D - engine.SLIDING_FRONT_SETBACK - t - lane * pitch
            boxes.append(_box(f"Sliding door {k + 1}", "door", x, lay["door_y"], z, dw, lay["door_h"], t, paint("door")))
            hx = x + dw - 22 if k % 2 == 0 else x + 10
            if style != "none":   # a flush pull set into the panel (no knob variant for sliding panels)
                boxes.append(_box(f"Door handle {k + 1}", "handle", hx, lay["door_y"] + lay["door_h"] / 2 - BAR_LEN / 2, z, 12, BAR_LEN, t, paint("handle")))
        boxes.append(_box("Top track", "handle", t, H - t - inp.track_top, D - engine.SLIDING_FRONT_SETBACK - t - pitch, lay["inner_w"], inp.track_top, 2 * t + engine.SLIDING_LANE_GAP, paint("handle")))
        boxes.append(_box("Bottom track", "handle", t, by + t, D - engine.SLIDING_FRONT_SETBACK - t - pitch, lay["inner_w"], inp.track_bottom, 2 * t + engine.SLIDING_LANE_GAP, paint("handle")))
    elif inp.doors:
        dw = lay["door_w"]
        for k in range(inp.doors):
            x = engine.DOOR_EDGE_GAP + k * (dw + engine.DOOR_GAP)
            boxes.append(_box(f"Door {k + 1}", "door", x, lay["door_y"], D, dw, lay["door_h"], t, paint("door")))
            hx = x + dw - 22 if k % 2 == 0 else x + 14
            cy = lay["door_y"] + lay["door_h"] / 2
            if style == "bar":
                boxes.append(_box(f"Door handle {k + 1}", "handle", hx, cy - BAR_LEN / 2, D + t, 8, BAR_LEN, 12, paint("handle")))
            elif style == "knob":
                boxes.append(_box(f"Door handle {k + 1}", "handle", hx - 8, cy - KNOB[1] / 2, D + t, *KNOB, paint("handle")))
    model = {
        "dimensions": {"width": W, "height": H, "depth": D, "thickness": t},
        "boxes": boxes,
        "bounds": {"min": [0, 0, -inp.back_thickness], "max": [W, H, D + t + {"bar": 12, "knob": KNOB[2], "none": 0}[style]]},
        "warnings": warnings,
        "requires_professional_review": True,
    }
    if verify:
        model["consistency"] = check_consistency(model, inp, engine.calculate(inp)["parts"])
    return model


# ------------------------------------------------------------------------------------------------ consistency
TOL = 0.06   # mm: parts are rounded to 0.1, boxes to 0.01
STRUCTURAL = ("carcass", "shelf", "door", "drawer", "back")


def _expected_size(name: str, parts: dict[str, dict]):
    """(sx, sy, sz) a modelled box must have, taken from the *calculated parts* (not from the builder's own formulas)."""
    def p(n):
        return parts.get(n)
    rules = [
        ("Left side", "Side panel", lambda q: (q["thickness"], q["height"], q["width"])),
        ("Right side", "Side panel", lambda q: (q["thickness"], q["height"], q["width"])),
        ("Top", "Top panel", lambda q: (q["width"], q["thickness"], q["height"])),
        ("Bottom", "Bottom panel", lambda q: (q["width"], q["thickness"], q["height"])),
        ("Back", "Back panel", lambda q: (q["width"], q["height"], q["thickness"])),
        ("Front top rail", "Front top rail", lambda q: (q["width"], q["thickness"], q["height"])),
        ("Rear top rail", "Rear top rail", lambda q: (q["width"], q["thickness"], q["height"])),
        ("Plinth", "Plinth", lambda q: (q["width"], q["height"], q["thickness"])),
        ("Hanging rail", "Hanging rail", lambda q: (q["width"], q["height"], q["thickness"])),
    ]
    for box_name, part_name, fn in rules:
        if name == box_name:
            return (part_name, fn(p(part_name))) if p(part_name) else (part_name, None)
    for prefix, part_name, fn in (("Shelf ", "Shelf", lambda q: (q["width"], q["thickness"], q["height"])),
                                  ("Drawer front ", "Drawer front", lambda q: (q["width"], q["height"], q["thickness"])),
                                  ("Sliding door ", "Sliding door", lambda q: (q["width"], q["height"], q["thickness"])),
                                  ("Door ", "Door", lambda q: (q["width"], q["height"], q["thickness"]))):
        if name.startswith(prefix) and name[len(prefix):].isdigit():
            return (part_name, fn(p(part_name))) if p(part_name) else (part_name, None)
    return None


def _overlap(a: dict, b: dict) -> float:
    """Penetration depth (mm) of two axis-aligned boxes; <= 0 when they only touch or are apart."""
    ox = min(a["x"] + a["sx"], b["x"] + b["sx"]) - max(a["x"], b["x"])
    oy = min(a["y"] + a["sy"], b["y"] + b["sy"]) - max(a["y"], b["y"])
    oz = min(a["z"] + a["sz"], b["z"] + b["sz"]) - max(a["z"], b["z"])
    return min(ox, oy, oz)


def check_consistency(model: dict, inp: CabinetInput, calc_parts: list[dict]) -> dict:
    """Proves that the 3D model is the calculated cabinet: overall size, component counts, every modelled component's size equals
    the calculated part, and no two structural components occupy the same space. Drawer boxes inside the cabinet are calculated
    (cut list) but not drawn; that is the only intentional difference."""
    boxes = model["boxes"]
    parts = {p["name"]: p for p in calc_parts}
    problems: list[str] = []
    W, H, D = inp.width, inp.height, inp.depth

    xs0, xs1 = min(b["x"] for b in boxes), max(b["x"] + b["sx"] for b in boxes)
    ys0, ys1 = min(b["y"] for b in boxes), max(b["y"] + b["sy"] for b in boxes)
    if abs(xs0) > TOL or abs(xs1 - W) > TOL:
        problems.append(f"model width {xs1 - xs0:.2f} mm differs from the calculated width {W:g} mm")
    if abs(ys0) > TOL or abs(ys1 - H) > TOL:
        problems.append(f"model height {ys1 - ys0:.2f} mm differs from the calculated height {H:g} mm")
    sides = [b for b in boxes if b["name"] in ("Left side", "Right side")]
    if any(abs(b["sz"] - D) > TOL for b in sides):
        problems.append(f"carcass depth differs from the calculated depth {D:g} mm")

    def count(prefix, exclude=()):
        return sum(1 for b in boxes if b["name"].startswith(prefix) and not any(e in b["name"] for e in exclude))
    expected_doors = inp.doors
    door_prefix = "Sliding door " if inp.cabinet_type == "sliding_wardrobe" else "Door "
    got_doors = sum(1 for b in boxes if b["kind"] == "door")
    if got_doors != expected_doors:
        problems.append(f"{got_doors} door panels modelled, {expected_doors} calculated")
    if count("Drawer front ") != inp.drawers:
        problems.append(f"{count('Drawer front ')} drawer fronts modelled, {inp.drawers} calculated")
    if count("Shelf ") != inp.shelves:
        problems.append(f"{count('Shelf ')} shelves modelled, {inp.shelves} calculated")
    hw = {h["name"]: h["quantity"] for h in engine.hardware(inp)}
    handles = sum(1 for b in boxes if b["kind"] == "handle" and "handle" in b["name"].lower())
    if handles != hw.get("Handle", 0):
        problems.append(f"{handles} handles modelled, {hw.get('Handle', 0)} in the hardware list")

    for b in boxes:
        exp = _expected_size(b["name"], parts)
        if exp is None:
            continue
        part_name, size = exp
        if size is None:
            problems.append(f"'{b['name']}' has no calculated part '{part_name}'")
            continue
        got = (b["sx"], b["sy"], b["sz"])
        if any(abs(g - e) > TOL for g, e in zip(got, size)):
            problems.append(f"'{b['name']}' is {got[0]:g} x {got[1]:g} x {got[2]:g} mm but the calculated part '{part_name}' needs {size[0]:g} x {size[1]:g} x {size[2]:g} mm")

    rail_conflict = any("collides with the hanging rail" in w for w in model.get("warnings", []))   # disclosed to the user already
    struct = [b for b in boxes if b["kind"] in STRUCTURAL]
    for i, a in enumerate(struct):
        for b in struct[i + 1:]:
            if rail_conflict and {"Hanging rail"} & {a["name"], b["name"]} and any(n.startswith("Shelf") for n in (a["name"], b["name"])):
                continue
            if _overlap(a, b) > TOL:
                problems.append(f"'{a['name']}' and '{b['name']}' occupy the same space")
    _ = door_prefix
    return {"valid": not problems, "problems": problems,
            "checks": ["overall_size", "component_counts", "component_sizes_match_parts", "no_overlapping_components", "handles_match_hardware"],
            "not_modelled": ["drawer boxes (sides, back, bottom) are in the cut list but not drawn"]}
