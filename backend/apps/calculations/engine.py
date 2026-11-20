"""Cabinet calculation engine — pure Python, no Django, no external AI.

All dimensions are millimetres. Formulas are explicit and the assumptions behind
them are returned with every result so a professional can review them.
Outputs are NOT verified manufacturing instructions.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from math import floor

LIMITS = {
    "width": (200, 4000),
    "height": (200, 3000),
    "depth": (150, 1000),
    "thickness": (8, 40),
    "back_thickness": (3, 8),
    "shelves": (0, 20),
    "doors": (0, 6),
    "drawers": (0, 10),
}

DOOR_GAP = 3          # between doors
DOOR_EDGE_GAP = 2     # door to carcass edge
SHELF_SETBACK = 20    # shelf depth reduction (front recess is not modelled; shelves sit 20 mm shallower)
BACK_CLEARANCE = 4    # overlay back panel is 4 mm smaller than carcass in both directions
SLIDE_CLEARANCE = 13  # per side, for ball-bearing drawer slides
DRAWER_BOX_T = 16
DRAWER_DEPTH_LOSS = 50
MIN_DRAWER_FRONT = 80
MIN_DOOR_WIDTH = 100
DRAWER_FRONT_GAP = 3
STD_WASTE_FACTOR = 0.15  # used only for the quick area-based sheet estimate


class EngineValidationError(ValueError):
    def __init__(self, errors: dict[str, str]):
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))
        self.errors = errors


@dataclass
class CabinetInput:
    width: float
    height: float
    depth: float
    thickness: float = 18
    shelves: int = 0
    doors: int = 0
    drawers: int = 0
    back_thickness: float = 4
    material: str = "MDF"
    back_material: str = "HDF"

    @classmethod
    def from_dict(cls, d: dict) -> "CabinetInput":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class Part:
    name: str
    width: float          # mm, across-grain nominal
    height: float         # mm, along-grain nominal (long direction of the part as installed)
    thickness: float
    quantity: int
    material: str
    can_rotate: bool = False
    edge_w: int = 0       # number of edges banded along the `width` side
    edge_h: int = 0       # number of edges banded along the `height` side
    edge_note: str = ""
    group: str = "carcass"

    @property
    def area_m2(self) -> float:
        return self.width * self.height * self.quantity / 1_000_000

    @property
    def edge_length_mm(self) -> float:
        return (self.edge_w * self.width + self.edge_h * self.height) * self.quantity

    def to_dict(self) -> dict:
        d = asdict(self)
        d["area_m2"] = round(self.area_m2, 4)
        d["edge_length_mm"] = round(self.edge_length_mm, 1)
        return d


def _num(inp: CabinetInput):
    for k in ("width", "height", "depth", "thickness", "back_thickness"):
        v = getattr(inp, k)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise EngineValidationError({k: "must be a number"})
    for k in ("shelves", "doors", "drawers"):
        v = getattr(inp, k)
        if isinstance(v, bool) or not isinstance(v, int):
            raise EngineValidationError({k: "must be a whole number"})


def layout(inp: CabinetInput) -> dict:
    """Derived vertical layout shared by the calculator and the 3D builder."""
    t = inp.thickness
    inner_h = inp.height - 2 * t
    inner_w = inp.width - 2 * t
    levels = inp.drawers + inp.shelves + 1  # equal slots: drawers at the bottom, then shelves, one open slot on top
    slot_h = inner_h / levels
    drawer_front_h = floor(slot_h) - DRAWER_FRONT_GAP if inp.drawers else 0
    drawers_zone = inp.drawers * (drawer_front_h + DRAWER_FRONT_GAP) if inp.drawers else 0
    if inp.doors:
        if inp.drawers:
            door_h = inp.height - 2 * DOOR_EDGE_GAP - drawers_zone - t
            door_y = DOOR_EDGE_GAP + drawers_zone + t
        else:
            door_h = inp.height - 2 * DOOR_EDGE_GAP
            door_y = DOOR_EDGE_GAP
        door_w = (inp.width - 2 * DOOR_EDGE_GAP - (inp.doors - 1) * DOOR_GAP) / inp.doors
    else:
        door_h = door_y = door_w = 0
    return {"inner_w": inner_w, "inner_h": inner_h, "levels": levels, "slot_h": slot_h,
            "drawer_front_h": drawer_front_h, "drawers_zone": drawers_zone,
            "door_w": door_w, "door_h": door_h, "door_y": door_y}


def validate(inp: CabinetInput) -> list[str]:
    """Raises EngineValidationError on hard errors; returns a list of warnings."""
    _num(inp)
    errors: dict[str, str] = {}
    for key, (lo, hi) in LIMITS.items():
        v = getattr(inp, key)
        if v < lo or v > hi:
            errors[key] = f"must be between {lo} and {hi}"
    if errors:
        raise EngineValidationError(errors)
    t = inp.thickness
    if 2 * t >= inp.width - 50:
        errors["thickness"] = "too thick for this width (internal width under 50 mm)"
    if 2 * t >= inp.height - 50:
        errors["thickness"] = "too thick for this height (internal height under 50 mm)"
    if errors:
        raise EngineValidationError(errors)

    lay = layout(inp)
    warnings: list[str] = []
    if inp.doors and lay["door_w"] < MIN_DOOR_WIDTH:
        errors["doors"] = f"doors would be narrower than {MIN_DOOR_WIDTH} mm"
    if inp.doors and lay["door_h"] < 100:
        errors["doors"] = "no vertical room left for doors above the drawers"
    if inp.drawers and lay["drawer_front_h"] < MIN_DRAWER_FRONT:
        errors["drawers"] = f"drawer fronts would be under {MIN_DRAWER_FRONT} mm high; reduce drawers/shelves"
    if inp.drawers and inp.depth - DRAWER_DEPTH_LOSS < 150:
        errors["depth"] = "too shallow for drawers"
    if inp.drawers and lay["inner_w"] - 2 * SLIDE_CLEARANCE - 2 * DRAWER_BOX_T < 60:
        errors["width"] = "too narrow for drawers"
    if errors:
        raise EngineValidationError(errors)

    if inp.doors and lay["door_w"] > 600:
        warnings.append(f"Door width {lay['door_w']:.0f} mm exceeds 600 mm; consider more doors to limit warping and hinge load.")
    if inp.doors and lay["door_h"] > 2200:
        warnings.append("Door height exceeds 2200 mm; check hinge count and door stability.")
    if lay["inner_w"] > 800 and t <= 18 and inp.shelves:
        warnings.append(f"Shelf span {lay['inner_w']:.0f} mm at {t:g} mm thickness may sag under load; consider a centre support or thicker board.")
    if inp.back_thickness > 6 and inp.back_material.upper() == "HDF":
        warnings.append("Back thickness above 6 mm is unusual for HDF.")
    if inp.depth < 250 and inp.shelves:
        warnings.append("Very shallow carcass; check shelf usability.")
    return warnings


def build_parts(inp: CabinetInput) -> list[Part]:
    t, W, H, D = inp.thickness, inp.width, inp.height, inp.depth
    lay = layout(inp)
    m = inp.material
    parts: list[Part] = [
        Part("Side panel", D, H, t, 2, m, edge_h=1, edge_note="front edge (1 x height)"),
        Part("Top panel", lay["inner_w"], D, t, 1, m, edge_w=1, edge_note="front edge (1 x width)"),
        Part("Bottom panel", lay["inner_w"], D, t, 1, m, edge_w=1, edge_note="front edge (1 x width)"),
    ]
    if inp.shelves:
        parts.append(Part("Shelf", lay["inner_w"], D - SHELF_SETBACK, t, inp.shelves, m, edge_w=1, edge_note="front edge (1 x width)"))
    parts.append(Part("Back panel", W - BACK_CLEARANCE, H - BACK_CLEARANCE, inp.back_thickness, 1, inp.back_material,
                      can_rotate=True, edge_note="no edge banding", group="back"))
    if inp.doors:
        parts.append(Part("Door", round(lay["door_w"], 1), round(lay["door_h"], 1), t, inp.doors, m, edge_w=2, edge_h=2,
                          edge_note="all 4 edges", group="fronts"))
    if inp.drawers:
        n = inp.drawers
        ext_w = lay["inner_w"] - 2 * SLIDE_CLEARANCE
        box_len = D - DRAWER_DEPTH_LOSS
        box_h = lay["drawer_front_h"] - 30
        parts += [
            Part("Drawer front", lay["inner_w"] - 4, lay["drawer_front_h"], t, n, m, edge_w=2, edge_h=2, edge_note="all 4 edges", group="fronts"),
            Part("Drawer side", box_len, box_h, DRAWER_BOX_T, 2 * n, m, edge_w=1, edge_note="top edge (1 x length)", group="drawer"),
            Part("Drawer back", ext_w - 2 * DRAWER_BOX_T, box_h - 10, DRAWER_BOX_T, n, m, edge_note="no edge banding", group="drawer"),
            Part("Drawer inner front", ext_w - 2 * DRAWER_BOX_T, box_h, DRAWER_BOX_T, n, m, edge_w=1, edge_note="top edge (1 x width)", group="drawer"),
            Part("Drawer bottom", ext_w - 10, box_len - 10, inp.back_thickness, n, inp.back_material, can_rotate=True,
                 edge_note="no edge banding", group="drawer"),
        ]
    for p in parts:
        p.width, p.height = round(p.width, 1), round(p.height, 1)
    return parts


ASSUMPTIONS = [
    "Overlay (surface-mounted) back panel, 4 mm smaller than the carcass in both directions.",
    "Sides run full height; top and bottom panels sit between the sides.",
    "Shelves are 20 mm shallower than the carcass depth.",
    "Doors are overlay doors with 2 mm edge gaps and 3 mm gaps between doors; when drawers are present, doors cover only the area above the drawers.",
    "Drawers, shelves and one open top compartment share the internal height in equal slots; drawers occupy the bottom slots.",
    "Drawer boxes use 16 mm board, 13 mm clearance per side for ball-bearing slides and a box length of depth minus 50 mm.",
    "Edge banding is applied to visible front edges as listed per part.",
    "Hinge, slide, handle and fastener hardware is not calculated.",
]


def calculate(data: dict | CabinetInput) -> dict:
    inp = data if isinstance(data, CabinetInput) else CabinetInput.from_dict(data)
    warnings = validate(inp)
    parts = build_parts(inp)
    by_material: dict[str, dict] = {}
    for p in parts:
        key = f"{p.material} {p.thickness:g} mm"
        g = by_material.setdefault(key, {"material": p.material, "thickness": p.thickness, "area_m2": 0.0, "parts": 0})
        g["area_m2"] += p.area_m2
        g["parts"] += p.quantity
    for g in by_material.values():
        g["area_m2"] = round(g["area_m2"], 4)
        g["estimated_area_with_waste_m2"] = round(g["area_m2"] * (1 + STD_WASTE_FACTOR), 4)
    total_area = round(sum(p.area_m2 for p in parts), 4)
    edge_m = round(sum(p.edge_length_mm for p in parts) / 1000, 2)
    return {
        "input": asdict(inp),
        "parts": [p.to_dict() for p in parts],
        "summary": {
            "panel_count": sum(p.quantity for p in parts),
            "distinct_parts": len(parts),
            "total_area_m2": total_area,
            "edge_banding_m": edge_m,
            "waste_factor_assumed": STD_WASTE_FACTOR,
            "by_material": by_material,
            "layout": {k: round(v, 1) if isinstance(v, float) else v for k, v in layout(inp).items()},
        },
        "warnings": warnings,
        "assumptions": ASSUMPTIONS,
        "requires_professional_review": True,
        "disclaimer": "Calculated output for professional review. Not verified for manufacture.",
    }


def sheets_by_area(area_m2: float, sheet_w_mm: float, sheet_h_mm: float, waste: float = STD_WASTE_FACTOR) -> int:
    from math import ceil
    return max(1, ceil(area_m2 * (1 + waste) / (sheet_w_mm * sheet_h_mm / 1_000_000)))
