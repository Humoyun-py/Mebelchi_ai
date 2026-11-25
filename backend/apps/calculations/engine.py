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
    "edge_thickness": (0, 3),      # mm of edge banding tape; 0 = cut sizes equal finished sizes
    "plinth_height": (60, 200),    # kitchen base cabinets only
    "sliding_overlap": (10, 100),  # sliding wardrobes only: overlap of neighbouring panels
    "track_top": (0, 80),          # sliding wardrobes only: height taken by the top track
    "track_bottom": (0, 80),       # sliding wardrobes only: height taken by the bottom track
    "rail_width": (50, 300),       # kitchen base top rails / wall-cabinet hanging rail
}

CABINET_TYPES = ("standard", "kitchen_base", "kitchen_wall", "sliding_wardrobe")
HANDLE_STYLES = ("bar", "knob", "none")

DOOR_GAP = 3          # between doors
DOOR_EDGE_GAP = 2     # door to carcass edge
SHELF_SETBACK = 20    # shelf depth reduction (front recess is not modelled; shelves sit 20 mm shallower)
BACK_CLEARANCE = 4    # overlay back panel is 4 mm smaller than carcass in both directions
SLIDE_CLEARANCE = 13  # per side, for ball-bearing drawer slides
DRAWER_BOX_T = 16
DRAWER_DEPTH_LOSS = 50
MIN_DRAWER_FRONT = 80
MIN_SHELF_GAP = 30     # clear opening between two shelves (or a shelf and a panel)
MIN_DOOR_WIDTH = 100
DRAWER_FRONT_GAP = 3
STD_WASTE_FACTOR = 0.15  # used only for the quick area-based sheet estimate
SLIDING_FRONT_SETBACK = 20  # front sliding lane face is this far behind the carcass front
SLIDING_LANE_GAP = 4        # clearance between the two sliding lanes (lane pitch = thickness + gap)
SLIDING_SHELF_CLEARANCE = 5  # shelves stop this far behind the rear sliding lane
SLIDING_MAX_PANEL_W = 1200  # advisory limit used for a warning only
SLIDING_MAX_PANEL_H = 2700
WALL_MAX_DEPTH = 400        # advisory limit used for a warning only


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
    cabinet_type: str = "standard"   # standard | kitchen_base | kitchen_wall | sliding_wardrobe
    edge_thickness: float = 0        # mm
    plinth_height: float = 100       # kitchen_base
    sliding_overlap: float = 30      # sliding_wardrobe
    track_top: float = 35            # sliding_wardrobe
    track_bottom: float = 20         # sliding_wardrobe
    rail_width: float = 100          # kitchen_base top rails, kitchen_wall hanging rail
    handle_style: str = "bar"        # bar | knob | none (none = handleless; the hardware list then has no handles)

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

    def cut_size(self, edge_thickness: float) -> tuple[float, float]:
        """Size to cut from the sheet so that the *finished* size is reached after banding.

        An edge running along the `width` side closes the `height` dimension and vice versa, so each banded edge
        removes one tape thickness from the dimension it closes."""
        return round(self.width - self.edge_h * edge_thickness, 2), round(self.height - self.edge_w * edge_thickness, 2)

    def to_dict(self, edge_thickness: float = 0) -> dict:
        d = asdict(self)
        d["cut_width"], d["cut_height"] = self.cut_size(edge_thickness)
        d["area_m2"] = round(self.area_m2, 4)
        d["edge_length_mm"] = round(self.edge_length_mm, 1)
        return d


def _num(inp: CabinetInput):
    for k in ("width", "height", "depth", "thickness", "back_thickness", "edge_thickness", "plinth_height",
              "sliding_overlap", "track_top", "track_bottom", "rail_width"):
        v = getattr(inp, k)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v in (float("inf"), float("-inf")):
            raise EngineValidationError({k: "must be a number"})
    for k in ("shelves", "doors", "drawers"):
        v = getattr(inp, k)
        if isinstance(v, bool) or not isinstance(v, int):
            raise EngineValidationError({k: "must be a whole number"})
    if inp.cabinet_type not in CABINET_TYPES:
        raise EngineValidationError({"cabinet_type": f"must be one of: {', '.join(CABINET_TYPES)}"})
    if inp.handle_style not in HANDLE_STYLES:
        raise EngineValidationError({"handle_style": f"must be one of: {', '.join(HANDLE_STYLES)}"})


def layout(inp: CabinetInput) -> dict:
    """Derived vertical layout shared by the calculator and the 3D builder.

    `body_h` is the carcass height (the total height minus the plinth for kitchen base cabinets) and `base_y` is the
    height of the carcass underside above the floor. For every other type body_h == height and base_y == 0."""
    t = inp.thickness
    base = inp.cabinet_type == "kitchen_base"
    sliding = inp.cabinet_type == "sliding_wardrobe"
    base_y = inp.plinth_height if base else 0
    body_h = inp.height - base_y
    inner_h = body_h - 2 * t
    inner_w = inp.width - 2 * t
    levels = inp.drawers + inp.shelves + 1  # equal slots: drawers at the bottom, then shelves, one open slot on top
    slot_h = inner_h / levels
    drawer_front_h = floor(slot_h) - DRAWER_FRONT_GAP if inp.drawers else 0
    drawers_zone = inp.drawers * (drawer_front_h + DRAWER_FRONT_GAP) if inp.drawers else 0
    if inp.doors and sliding:
        # Panels sit inside the carcass between the side panels. Neighbouring panels overlap by `sliding_overlap`, so
        # n * w - (n - 1) * overlap = inner_w. The panel height is the opening minus the two track allowances.
        n = inp.doors
        door_w = (inner_w + (n - 1) * inp.sliding_overlap) / n
        door_h = inner_h - inp.track_top - inp.track_bottom
        door_y = base_y + t + inp.track_bottom
    elif inp.doors:
        if inp.drawers:
            door_h = body_h - 2 * DOOR_EDGE_GAP - drawers_zone - t
            door_y = base_y + DOOR_EDGE_GAP + drawers_zone + t
        else:
            door_h = body_h - 2 * DOOR_EDGE_GAP
            door_y = base_y + DOOR_EDGE_GAP
        door_w = (inp.width - 2 * DOOR_EDGE_GAP - (inp.doors - 1) * DOOR_GAP) / inp.doors
    else:
        door_h = door_y = door_w = 0
    return {"inner_w": inner_w, "inner_h": inner_h, "levels": levels, "slot_h": slot_h,
            "drawer_front_h": drawer_front_h, "drawers_zone": drawers_zone,
            "door_w": door_w, "door_h": door_h, "door_y": door_y, "body_h": body_h, "base_y": base_y}


def shelf_depth(inp: CabinetInput) -> float:
    """Depth of a shelf. Normally 20 mm less than the carcass; behind sliding doors it must also clear both door lanes."""
    if inp.cabinet_type == "sliding_wardrobe":
        return inp.depth - SLIDING_FRONT_SETBACK - 2 * inp.thickness - SLIDING_LANE_GAP - SLIDING_SHELF_CLEARANCE
    return inp.depth - SHELF_SETBACK


def _shelf_hits_hanging_rail(inp: CabinetInput, lay: dict) -> bool:
    """Shelves sit at equal slot boundaries; one collides with the hanging rail when it lies inside the rail's height band."""
    t = inp.thickness
    rail_lo, rail_hi = inp.height - t - inp.rail_width, inp.height - t
    for i in range(inp.drawers + 1, lay["levels"]):
        y = lay["base_y"] + t + lay["slot_h"] * i - t / 2
        if y < rail_hi and y + t > rail_lo:
            return True
    return False


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
    body_h = inp.height - (inp.plinth_height if inp.cabinet_type == "kitchen_base" else 0)
    if 2 * t >= inp.width - 50:
        errors["thickness"] = "too thick for this width (internal width under 50 mm)"
    if 2 * t >= body_h - 50:
        errors["thickness"] = "too thick for this height (internal height under 50 mm)"
    if inp.cabinet_type == "kitchen_base" and body_h < 200:
        errors["plinth_height"] = "leaves less than 200 mm for the cabinet body"
    if inp.cabinet_type == "kitchen_wall" and inp.drawers:
        errors["drawers"] = "wall cabinets cannot carry drawers"
    if inp.cabinet_type == "sliding_wardrobe":
        if inp.doors < 2:
            errors["doors"] = "a sliding wardrobe needs at least 2 sliding doors"
        if inp.drawers:
            errors["drawers"] = "sliding wardrobes do not take drawers behind the sliding doors in this calculator"
    if errors:
        raise EngineValidationError(errors)

    lay = layout(inp)
    warnings: list[str] = []
    sliding = inp.cabinet_type == "sliding_wardrobe"
    if inp.doors and lay["door_w"] < MIN_DOOR_WIDTH:
        errors["doors"] = f"doors would be narrower than {MIN_DOOR_WIDTH} mm"
    if inp.doors and lay["door_h"] < 100:
        errors["doors"] = "no vertical room left for doors above the drawers" if not sliding else "no vertical room left for sliding doors after the track allowances"
    if inp.drawers and lay["drawer_front_h"] < MIN_DRAWER_FRONT:
        errors["drawers"] = f"drawer fronts would be under {MIN_DRAWER_FRONT} mm high; reduce drawers/shelves"
    if inp.drawers and inp.depth - DRAWER_DEPTH_LOSS < 150:
        errors["depth"] = "too shallow for drawers"
    if inp.drawers and lay["inner_w"] - 2 * SLIDE_CLEARANCE - 2 * DRAWER_BOX_T < 60:
        errors["width"] = "too narrow for drawers"
    if sliding and inp.depth < 2 * t + SLIDING_FRONT_SETBACK + 2 * SLIDING_LANE_GAP + 50:
        errors["depth"] = "too shallow for two sliding lanes"
    if inp.shelves and lay["slot_h"] - t < MIN_SHELF_GAP:
        errors["shelves"] = f"too many shelves/drawers for this height (the clear opening would be under {MIN_SHELF_GAP} mm)"
    if inp.cabinet_type == "kitchen_base" and 2 * inp.rail_width > inp.depth:
        errors["rail_width"] = "the front and rear top rails would overlap (rail width x 2 is larger than the depth)"
    if inp.cabinet_type == "kitchen_wall" and inp.rail_width > lay["inner_h"] - 20:
        errors["rail_width"] = "the hanging rail is taller than the cabinet interior"
    if sliding and inp.shelves and shelf_depth(inp) < 100:
        errors["depth"] = "too shallow for shelves behind the sliding doors (shelf depth would be under 100 mm)"
    if sliding and inp.doors >= 3 and lay["door_w"] <= 2 * inp.sliding_overlap:
        # panels k and k+2 share a lane; they would touch or overlap in plan
        errors["sliding_overlap"] = "too large for this number of panels (panels in the same lane would collide)"
    if errors:
        raise EngineValidationError(errors)

    if sliding:
        if lay["door_w"] > SLIDING_MAX_PANEL_W:
            warnings.append(f"Sliding panel width {lay['door_w']:.0f} mm exceeds {SLIDING_MAX_PANEL_W} mm; check the rated load of the sliding system or add a panel.")
        if lay["door_h"] > SLIDING_MAX_PANEL_H:
            warnings.append(f"Sliding panel height {lay['door_h']:.0f} mm exceeds {SLIDING_MAX_PANEL_H} mm; check the sliding system limits.")
    else:
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
    if inp.cabinet_type == "kitchen_wall" and _shelf_hits_hanging_rail(inp, lay):
        warnings.append("A shelf position collides with the hanging rail at the top; reduce the shelves or the rail width, or notch the shelf.")
    if inp.cabinet_type == "kitchen_wall" and inp.depth > WALL_MAX_DEPTH:
        warnings.append(f"Wall cabinet depth {inp.depth:g} mm exceeds {WALL_MAX_DEPTH} mm; check the wall fixing capacity and reach.")
    return warnings


def build_parts(inp: CabinetInput) -> list[Part]:
    t, W, H, D = inp.thickness, inp.width, inp.height, inp.depth
    lay = layout(inp)
    m = inp.material
    body_h = lay["body_h"]
    kind = inp.cabinet_type
    parts: list[Part] = [Part("Side panel", D, body_h, t, 2, m, edge_h=1, edge_note="front edge (1 x height)")]
    if kind == "kitchen_base":
        # Open top: a front and a rear rail replace the full top panel, which keeps the worktop fixable and the cabinet light.
        parts.append(Part("Front top rail", lay["inner_w"], inp.rail_width, t, 1, m, edge_w=1, edge_note="front edge (1 x width)"))
        parts.append(Part("Rear top rail", lay["inner_w"], inp.rail_width, t, 1, m, edge_note="no edge banding"))
    else:
        parts.append(Part("Top panel", lay["inner_w"], D, t, 1, m, edge_w=1, edge_note="front edge (1 x width)"))
    parts.append(Part("Bottom panel", lay["inner_w"], D, t, 1, m, edge_w=1, edge_note="front edge (1 x width)"))
    if kind == "kitchen_wall":
        parts.append(Part("Hanging rail", lay["inner_w"], inp.rail_width, t, 1, m, edge_note="no edge banding"))
    if kind == "kitchen_base":
        parts.append(Part("Plinth", W, inp.plinth_height, t, 1, m, edge_w=1, edge_note="top edge (1 x width)", group="fronts"))
    if inp.shelves:
        parts.append(Part("Shelf", lay["inner_w"], shelf_depth(inp), t, inp.shelves, m, edge_w=1, edge_note="front edge (1 x width)"))
    parts.append(Part("Back panel", W - BACK_CLEARANCE, body_h - BACK_CLEARANCE, inp.back_thickness, 1, inp.back_material,
                      can_rotate=True, edge_note="no edge banding", group="back"))
    if inp.doors:
        name = "Sliding door" if kind == "sliding_wardrobe" else "Door"
        parts.append(Part(name, round(lay["door_w"], 1), round(lay["door_h"], 1), t, inp.doors, m, edge_w=2, edge_h=2,
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


def hardware(inp: CabinetInput) -> list[dict]:
    """Estimated hardware counts. Rule-of-thumb values for professional review, not manufacturer data."""
    from math import ceil
    lay = layout(inp)
    items: list[dict] = []
    sliding = inp.cabinet_type == "sliding_wardrobe"

    def add(name: str, qty: int, note: str):
        if qty > 0:
            items.append({"name": name, "quantity": qty, "note": note})

    if inp.doors and sliding:
        add("Sliding track (top)", 1, f"1 track, length {lay['inner_w']:.0f} mm, 2 lanes")
        add("Sliding track (bottom)", 1, f"1 track, length {lay['inner_w']:.0f} mm, 2 lanes")
        add("Sliding roller set", inp.doors, "1 set (2 top + 2 bottom rollers) per sliding door")
    elif inp.doors:
        h = lay["door_h"]
        per = 2 if h <= 900 else 3 if h <= 1500 else 4 if h <= 2000 else 5
        if lay["door_w"] > 600:
            per += 1
        add("Hinge", per * inp.doors, f"{per} per door (door height {h:.0f} mm, width {lay['door_w']:.0f} mm)")
    add("Drawer slide (pair)", inp.drawers, "1 pair per drawer")
    if inp.handle_style != "none":
        add("Handle", inp.doors + inp.drawers, "1 per door and per drawer front" + (" (knob)" if inp.handle_style == "knob" else ""))
    add("Shelf pin", 4 * inp.shelves, "4 per adjustable shelf")
    if inp.cabinet_type == "kitchen_base":
        add("Adjustable leg", 4 + (2 if inp.width > 900 else 0), "4 corner legs, +2 centre legs when wider than 900 mm")
    if inp.cabinet_type == "kitchen_wall":
        add("Wall hanging bracket", 2, "1 per side, fixed to the hanging rail")
    per_joint = max(2, ceil(inp.depth / 200))
    add("Confirmat screw", 4 * per_joint, f"4 carcass joints x {per_joint} (about one per 200 mm of depth)")
    perimeter = 2 * ((inp.width - BACK_CLEARANCE) + (lay["body_h"] - BACK_CLEARANCE))
    add("Back panel fixing", ceil(perimeter / 200), "about one per 200 mm of back-panel perimeter")
    return items


ASSUMPTIONS = [
    "Overlay (surface-mounted) back panel, 4 mm smaller than the carcass in both directions.",
    "Sides run full height; top and bottom panels sit between the sides.",
    "Shelves are 20 mm shallower than the carcass depth.",
    "Doors are overlay doors with 2 mm edge gaps and 3 mm gaps between doors; when drawers are present, doors cover only the area above the drawers.",
    "Drawers, shelves and one open top compartment share the internal height in equal slots; drawers occupy the bottom slots.",
    "Drawer boxes use 16 mm board, 13 mm clearance per side for ball-bearing slides and a box length of depth minus 50 mm.",
    "Edge banding is applied to visible front edges as listed per part.",
    "Hardware quantities are rule-of-thumb estimates (hinges by door height, one slide pair and handle per drawer, 4 shelf pins per shelf, "
    "confirmat screws per carcass joint, back-panel fixings at about 200 mm pitch). Check them against the actual hardware maker's tables.",
]

TYPE_ASSUMPTIONS = {
    "kitchen_base": [
        "Kitchen base cabinet: the total height includes the plinth; the carcass is (height - plinth height) tall and stands on adjustable legs.",
        "The plinth board is as wide as the cabinet and as tall as the plinth height (trim it to the floor clearance on site).",
        "The top is two rails (front and rear) of the configured rail width instead of a full top panel; only the front rail is edge banded.",
    ],
    "kitchen_wall": [
        "Kitchen wall cabinet: full top and bottom panels and a hanging rail of the configured rail width, fixed behind the top panel, that carries the wall brackets.",
        "Wall cabinets take no drawers. Wall fixings must be chosen for the wall material and the loaded weight.",
    ],
    "sliding_wardrobe": [
        "Sliding wardrobe: the panels run in two lanes (alternating) between the side panels; neighbouring panels overlap by the configured overlap so that "
        "n x panel width - (n - 1) x overlap = internal width.",
        "Panel height = internal height - top track allowance - bottom track allowance (configured values; they depend on the sliding system).",
        "Panels are the same board as the carcass and are banded on all 4 edges. Track and roller dimensions are system specific and are not modelled.",
        "Shelves are shallower than in other cabinets so that they clear both sliding lanes: depth - 20 mm front set-back - 2 x thickness - 4 mm lane gap - 5 mm clearance.",
    ],
}
EDGE_ASSUMPTION = ("Cut sizes: each banded edge removes one edge-tape thickness from the dimension it closes, so that the finished part "
                   "(cut size + tape) equals the nominal size. Parts report both `width/height` (finished) and `cut_width/cut_height`.")


def assumptions_for(inp: CabinetInput) -> list[str]:
    out = list(ASSUMPTIONS) + TYPE_ASSUMPTIONS.get(inp.cabinet_type, [])
    if inp.edge_thickness:
        out.append(EDGE_ASSUMPTION)
    if inp.handle_style == "none":
        out.append("Handleless design: no handles are included in the hardware list or the 3D model.")
    elif inp.handle_style == "knob":
        out.append("Knob handles: one knob per door and per drawer front.")
    return out


def calculate(data: dict | CabinetInput, prices: "PriceList | dict | None" = None) -> dict:
    inp = data if isinstance(data, CabinetInput) else CabinetInput.from_dict(data)
    pricelist = parse_prices(prices) if prices is not None else None  # validate before doing any work
    warnings = validate(inp)
    parts = build_parts(inp)
    et = inp.edge_thickness
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
    hw = hardware(inp)
    result = {
        "input": asdict(inp),
        "parts": [p.to_dict(et) for p in parts],
        "summary": {
            "panel_count": sum(p.quantity for p in parts),
            "distinct_parts": len(parts),
            "total_area_m2": total_area,
            "edge_banding_m": edge_m,
            "edge_banding_thickness_mm": et,
            "waste_factor_assumed": STD_WASTE_FACTOR,
            "by_material": by_material,
            "layout": {k: round(v, 1) if isinstance(v, float) else v for k, v in layout(inp).items()},
        },
        "hardware": hw,
        "warnings": warnings,
        "assumptions": assumptions_for(inp),
        "requires_professional_review": True,
        "disclaimer": "Calculated output for professional review. Not verified for manufacture.",
    }
    if pricelist is not None:
        result["pricing"] = price_estimate(result, pricelist)
    return result


def sheets_by_area(area_m2: float, sheet_w_mm: float, sheet_h_mm: float, waste: float = STD_WASTE_FACTOR) -> int:
    from math import ceil
    return max(1, ceil(area_m2 * (1 + waste) / (sheet_w_mm * sheet_h_mm / 1_000_000)))


# ------------------------------------------------------------------------------------------------ pricing
@dataclass
class PriceList:
    """Every price is supplied by the caller (or read from the user's material catalogue). The engine never invents a price:
    an item without a price is listed under `missing` and the result is flagged incomplete."""
    currency: str = ""
    board_price_per_m2: dict = field(default_factory=dict)   # "MDF 18" (material + thickness) or "MDF" -> price per m2 of board
    waste_factor: float = STD_WASTE_FACTOR                   # extra board bought on top of the net area
    edge_price_per_m: float | None = None                    # banding tape per running metre
    edge_allowance: float = 0.05                             # extra tape for trimming and start/end of each strip
    hardware_prices: dict = field(default_factory=dict)      # hardware name (as in `hardware`) -> unit price
    labor_per_m2: float | None = None                        # manufacturing labour/processing per m2 of net board area
    markup_pct: float = 0.0                                  # margin added on top of the manufacturing cost


def _price_number(key: str, v, lo: float = 0, hi: float = 1e9) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v < lo or v > hi:
        raise EngineValidationError({f"prices.{key}": f"must be a number between {lo:g} and {hi:g}"})
    return float(v)


def parse_prices(p: "PriceList | dict") -> PriceList:
    if isinstance(p, PriceList):
        d = asdict(p)
    elif isinstance(p, dict):
        d = dict(p)
    else:
        raise EngineValidationError({"prices": "must be an object"})
    unknown = set(d) - set(PriceList.__dataclass_fields__)
    if unknown:
        raise EngineValidationError({"prices": f"unknown fields: {', '.join(sorted(map(str, unknown)))}"})
    out = PriceList()
    cur = d.get("currency", "")
    if not isinstance(cur, str) or len(cur) > 8:
        raise EngineValidationError({"prices.currency": "must be a short text (max 8 characters)"})
    out.currency = cur
    for field_name in ("board_price_per_m2", "hardware_prices"):
        raw = d.get(field_name)
        raw = {} if raw is None else raw
        if not isinstance(raw, dict):
            raise EngineValidationError({f"prices.{field_name}": "must be an object of name -> price"})
        setattr(out, field_name, {str(k).strip(): _price_number(f"{field_name}.{k}", v) for k, v in raw.items()})
    out.waste_factor = _price_number("waste_factor", d.get("waste_factor", STD_WASTE_FACTOR), 0, 0.6)
    out.edge_allowance = _price_number("edge_allowance", d.get("edge_allowance", 0.05), 0, 0.5)
    out.markup_pct = _price_number("markup_pct", d.get("markup_pct", 0.0), 0, 300)
    for k in ("edge_price_per_m", "labor_per_m2"):
        v = d.get(k)
        setattr(out, k, None if v is None else _price_number(k, v))
    return out


def _lookup_board_price(prices: dict, material: str, thickness: float) -> tuple[float | None, str]:
    wanted = (f"{material} {thickness:g}".upper(), material.upper())
    folded = {k.upper(): (v, k) for k, v in prices.items()}
    for w in wanted:
        if w in folded:
            return folded[w][0], folded[w][1]
    return None, ""


def price_estimate(calc: dict, pl: PriceList) -> dict:
    """Cost breakdown for a calculation result. Pure arithmetic over the supplied prices; every figure can be re-derived
    from `lines` (amount = quantity x unit_price, rounded to 2 decimals; totals are the sums of the rounded amounts)."""
    lines: list[dict] = []
    missing: list[str] = []

    def line(category: str, item: str, qty: float, unit: str, unit_price: float | None, note: str = ""):
        amount = round(qty * unit_price, 2) if unit_price is not None else None
        lines.append({"category": category, "item": item, "quantity": round(qty, 4), "unit": unit, "unit_price": unit_price,
                      "amount": amount, "note": note})
        if unit_price is None:
            missing.append(f"{category}: {item}")

    s = calc["summary"]
    for g in s["by_material"].values():
        area = g["area_m2"] * (1 + pl.waste_factor)
        price, key = _lookup_board_price(pl.board_price_per_m2, g["material"], g["thickness"])
        line("board", f"{g['material']} {g['thickness']:g} mm", area, "m2", price,
             f"net {g['area_m2']:.4f} m2 + {pl.waste_factor * 100:g}% waste" + (f" (price key '{key}')" if key else ""))
    if s["edge_banding_m"] > 0:
        line("edge_banding", "Edge banding tape", s["edge_banding_m"] * (1 + pl.edge_allowance), "m", pl.edge_price_per_m,
             f"{s['edge_banding_m']} m net + {pl.edge_allowance * 100:g}% allowance")
    for h in calc["hardware"]:
        line("hardware", h["name"], h["quantity"], "pcs", pl.hardware_prices.get(h["name"]), h["note"])
    line("labor", "Manufacturing labour", s["total_area_m2"], "m2", pl.labor_per_m2, "per m2 of net board area")

    sub = {c: round(sum(l["amount"] for l in lines if l["category"] == c and l["amount"] is not None), 2)
           for c in ("board", "edge_banding", "hardware", "labor")}
    cost = round(sum(sub.values()), 2)
    markup = round(cost * pl.markup_pct / 100, 2)
    return {
        "currency": pl.currency,
        "complete": not missing,
        "missing": missing,
        "lines": lines,
        "subtotals": sub,
        "manufacturing_cost": cost,
        "markup_pct": pl.markup_pct,
        "markup_amount": markup,
        "total_price": round(cost + markup, 2),
        "basis": "Board = net area x (1 + waste factor) x price per m2. Totals include only priced lines; when `complete` is false "
                 "the figures are partial and the items in `missing` have no price. Estimate for professional review, not a quotation.",
    }
