from collections import defaultdict
from decimal import Decimal

from django.db.models import Q
from rest_framework.exceptions import ValidationError

from apps.materials.models import Material

from . import optimizer
from .models import CuttingList, CuttingPart, OptimizationRun


def create_from_calculation(owner, calc: dict, *, project=None, name: str | None = None,
                            sheet_length: int = 2800, sheet_width: int = 2070) -> CuttingList:
    """Create a cutting list and its parts from an engine.calculate() result. Used by the web app and the Telegram bot."""
    cl = CuttingList.objects.create(owner=owner, project=project, name=name or "Cabinet cutting list",
                                    sheet_length=sheet_length, sheet_width=sheet_width, source_inputs=calc["input"])
    CuttingPart.objects.bulk_create([
        CuttingPart(cutting_list=cl, name=p["name"], width=p["width"], height=p["height"], thickness=p["thickness"],
                    quantity=p["quantity"], material=p["material"], can_rotate=p["can_rotate"],
                    edge_w=p["edge_w"], edge_h=p["edge_h"], edge_note=p["edge_note"])
        for p in calc["parts"]
    ])
    return cl


def sheet_for(cl: CuttingList, material: str, thickness: float):
    m = (Material.objects.filter(Q(is_system=True) | Q(owner=cl.owner), kind__iexact=material, thickness=Decimal(str(thickness)))
         .order_by("is_system").first())
    if m:
        return m.sheet_length, m.sheet_width, (float(m.price_per_sheet) if m.price_per_sheet else None), m.name
    if material.upper() == "HDF":
        return 2440, 1830, None, "HDF"
    return cl.sheet_length, cl.sheet_width, None, material


def run_optimization(cl: CuttingList, allow_rotation: bool = True) -> OptimizationRun:
    parts = list(cl.parts.all())
    if not parts:
        raise ValidationError({"parts": "The cutting list has no parts."})
    groups = defaultdict(list)
    for p in parts:
        groups[(p.material, float(p.thickness))].append(p)
    out, tot_sheets, tot_parts_area, tot_sheet_area, tot_cost, unplaced = [], 0, 0.0, 0.0, 0.0, []
    cost_known = True
    for (material, thick), plist in sorted(groups.items()):
        length, width, price, label = sheet_for(cl, material, thick)
        try:
            res = optimizer.optimize([{"name": p.name, "width": float(p.width), "height": float(p.height), "quantity": p.quantity,
                                       "can_rotate": p.can_rotate} for p in plist], length, width, float(cl.kerf), float(cl.trim), allow_rotation)
        except optimizer.OptimizerError as e:
            raise ValidationError({"detail": str(e)})
        s = res["summary"]
        cost = round(price * s["sheet_count"], 2) if price is not None else None
        cost_known &= price is not None
        tot_cost += cost or 0
        tot_sheets += s["sheet_count"]
        tot_parts_area += s["parts_area_m2"]
        tot_sheet_area += s["total_sheet_area_m2"]
        unplaced += [{**u, "material": material, "thickness": thick} for u in res["unplaced"]]
        out.append({"key": f"{material} {thick:g} mm", "material": material, "material_label": label, "thickness": thick,
                    "price_per_sheet": price, "estimated_cost": cost, "result": res})
    result = {
        "groups": out,
        "summary": {"sheet_count": tot_sheets, "parts_area_m2": round(tot_parts_area, 4), "sheet_area_m2": round(tot_sheet_area, 4),
                    "utilization_pct": round(100 * tot_parts_area / tot_sheet_area, 2) if tot_sheet_area else 0,
                    "waste_pct": round(100 * (1 - tot_parts_area / tot_sheet_area), 2) if tot_sheet_area else 0,
                    "estimated_cost": round(tot_cost, 2) if cost_known else None, "unplaced_count": len(unplaced)},
        "unplaced": unplaced,
        "requires_professional_review": True,
        "disclaimer": "Cutting layout for professional review. Verify grain direction, defects and machine limits before cutting.",
    }
    return OptimizationRun.objects.create(cutting_list=cl, result=result, sheet_count=tot_sheets, utilization_pct=result["summary"]["utilization_pct"])
