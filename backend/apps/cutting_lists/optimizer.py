"""2D sheet cutting optimizer — guillotine shelf packing, pure Python.

Coordinate convention: sheet x axis = sheet length (grain direction), y axis = sheet width.
A part's `height` (its long/grain dimension as installed) maps to the x axis unless rotated.
Rows ("shelves") span the sheet width so every cut is a guillotine cut.
"""
from __future__ import annotations

from dataclasses import dataclass, field

MAX_PIECES = 2000
PALETTE = ["#3b82f6", "#22c55e", "#f59e0b", "#a855f7", "#06b6d4", "#ef4444", "#84cc16", "#ec4899", "#14b8a6", "#f97316"]


class OptimizerError(ValueError):
    pass


@dataclass
class Item:
    uid: int
    name: str
    along: float      # footprint along sheet x if not rotated
    across: float     # footprint along sheet y if not rotated
    can_rotate: bool


@dataclass
class Row:
    y: float
    h: float
    x: float = 0.0


@dataclass
class Sheet:
    rows: list[Row] = field(default_factory=list)
    placements: list[dict] = field(default_factory=list)


def _orientations(it: Item, mode: str) -> list[tuple[float, float, bool]]:
    base = (it.along, it.across, False)
    swap = (it.across, it.along, True)
    if not it.can_rotate:
        return [base]
    if mode == "long_along":
        return [base, swap] if it.along >= it.across else [swap, base]
    return [base, swap]


def _pack(items: list[Item], W: float, H: float, kerf: float, mode: str) -> list[Sheet]:
    sheets: list[Sheet] = []

    def place(sheet: Sheet, row: Row, it: Item, w: float, h: float, rot: bool):
        sheet.placements.append({"part_id": it.uid, "name": it.name, "x": round(row.x, 2), "y": round(row.y, 2),
                                 "w": w, "h": h, "rotated": rot})
        row.x += w + kerf

    for it in items:
        done = False
        # try existing rows, choosing the tightest vertical fit (best-fit)
        best = None
        for si, sheet in enumerate(sheets):
            for row in sheet.rows:
                for (w, h, rot) in _orientations(it, mode):
                    if h <= row.h + 1e-9 and row.x + w <= W + 1e-9:
                        waste = row.h - h
                        key = (waste, W - (row.x + w))
                        if best is None or key < best[0]:
                            best = (key, si, row, w, h, rot)
        if best:
            _, si, row, w, h, rot = best
            place(sheets[si], row, it, w, h, rot)
            continue
        # new row on an existing sheet
        for sheet in sheets:
            used = sheet.rows[-1].y + sheet.rows[-1].h + kerf if sheet.rows else 0.0
            for (w, h, rot) in _orientations(it, mode):
                if w <= W + 1e-9 and used + h <= H + 1e-9:
                    row = Row(y=used, h=h)
                    sheet.rows.append(row)
                    place(sheet, row, it, w, h, rot)
                    done = True
                    break
            if done:
                break
        if done:
            continue
        # new sheet
        sheet = Sheet()
        for (w, h, rot) in _orientations(it, mode):
            if w <= W + 1e-9 and h <= H + 1e-9:
                row = Row(y=0.0, h=h)
                sheet.rows.append(row)
                place(sheet, row, it, w, h, rot)
                sheets.append(sheet)
                done = True
                break
        if not done:  # pragma: no cover — oversize items are filtered before packing
            raise OptimizerError(f"Part '{it.name}' cannot be placed.")
    return sheets


def optimize(parts: list[dict], sheet_length: float, sheet_width: float, kerf: float = 3.0, trim: float = 10.0,
             allow_rotation: bool = True) -> dict:
    """parts: [{id?, name, width, height, quantity, can_rotate?}] (mm). Returns layout + statistics."""
    for label, v, lo, hi in (("sheet_length", sheet_length, 300, 6000), ("sheet_width", sheet_width, 300, 3500),
                             ("kerf", kerf, 0, 10), ("trim", trim, 0, 50)):
        if not isinstance(v, (int, float)) or isinstance(v, bool) or v < lo or v > hi:
            raise OptimizerError(f"{label} must be a number between {lo} and {hi}.")
    W, H = sheet_length - 2 * trim, sheet_width - 2 * trim
    if W <= 0 or H <= 0:
        raise OptimizerError("Trim is larger than the sheet.")

    items: list[Item] = []
    unplaced: list[dict] = []
    uid = 0
    for p in parts:
        try:
            w, h, q = float(p["width"]), float(p["height"]), int(p.get("quantity", 1))
        except (KeyError, TypeError, ValueError):
            raise OptimizerError("Every part needs numeric width, height and quantity.")
        if w <= 0 or h <= 0 or q <= 0:
            raise OptimizerError(f"Part '{p.get('name', '?')}' has non-positive dimensions or quantity.")
        rot = bool(p.get("can_rotate", False)) and allow_rotation
        fits = (h <= W and w <= H) or (rot and w <= W and h <= H)
        for _ in range(q):
            uid += 1
            if uid > MAX_PIECES:
                raise OptimizerError(f"Too many pieces (max {MAX_PIECES}).")
            if fits:
                items.append(Item(uid, p.get("name", f"Part {uid}"), h, w, rot))
            else:
                unplaced.append({"part_id": uid, "name": p.get("name", f"Part {uid}"), "width": w, "height": h,
                                 "reason": "larger than usable sheet area"})

    best_sheets: list[Sheet] | None = None
    best_key = None
    if items:
        strategies = [
            (lambda i: (-i.across, -i.along), "long_along"), (lambda i: (-i.across, -i.along), "any"),
            (lambda i: (-(i.along * i.across), -i.across), "long_along"), (lambda i: (-(i.along * i.across), -i.across), "any"),
            (lambda i: (-i.along, -i.across), "long_along"), (lambda i: (-max(i.along, i.across), -min(i.along, i.across)), "long_along"),
        ]
        for keyf, mode in strategies:
            ordered = sorted(items, key=keyf)
            sheets = _pack(ordered, W, H, kerf, mode)
            last = sheets[-1]
            free_last = H - (last.rows[-1].y + last.rows[-1].h) if last.rows else H
            key = (len(sheets), -free_last)
            if best_key is None or key < best_key:
                best_key, best_sheets = key, sheets

    names = sorted({p.get("name", "") for p in parts})
    color_of = {n: PALETTE[i % len(PALETTE)] for i, n in enumerate(names)}
    for s_ in best_sheets or []:
        for pl in s_.placements:
            pl["color"] = color_of.get(pl["name"], PALETTE[0])
    legend = []
    for n in names:
        mine = [p for p in parts if p.get("name", "") == n]
        legend.append({"name": n, "color": color_of[n], "quantity": sum(int(p.get("quantity", 1)) for p in mine), "width": float(mine[0]["width"]), "height": float(mine[0]["height"])})
    sheet_area = sheet_length * sheet_width
    out_sheets = []
    parts_area = 0.0
    for i, s in enumerate(best_sheets or [], 1):
        used = sum(pl["w"] * pl["h"] for pl in s.placements)
        parts_area += used
        out_sheets.append({"index": i, "placements": s.placements, "used_area_mm2": round(used, 1),
                           "utilization_pct": round(100 * used / sheet_area, 2)})
    n = len(out_sheets)
    total = n * sheet_area
    offcut = None
    if out_sheets:
        last = best_sheets[-1]
        y_end = last.rows[-1].y + last.rows[-1].h if last.rows else 0
        offcut = {"sheet_index": n, "length": sheet_length, "width": round(sheet_width - trim - y_end, 1),
                  "note": "usable strip remaining across the full length of the last sheet (before trim)"}
        offcut["area_m2"] = round(offcut["length"] * max(offcut["width"], 0) / 1e6, 4)
    return {
        "sheet": {"length": sheet_length, "width": sheet_width, "kerf": kerf, "trim": trim, "allow_rotation": allow_rotation},
        "sheets": out_sheets,
        "summary": {
            "sheet_count": n,
            "pieces_placed": len(items),
            "total_sheet_area_m2": round(total / 1e6, 4),
            "parts_area_m2": round(parts_area / 1e6, 4),
            "waste_area_m2": round((total - parts_area) / 1e6, 4),
            "utilization_pct": round(100 * parts_area / total, 2) if total else 0.0,
            "waste_pct": round(100 * (total - parts_area) / total, 2) if total else 0.0,
            "last_sheet_offcut": offcut,
        },
        "legend": legend,
        "unplaced": unplaced,
        "requires_professional_review": True,
        "disclaimer": "Cutting layout for professional review. Verify grain direction, defects and machine limits before cutting.",
    }
