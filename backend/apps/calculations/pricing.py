"""Price inputs that come from the user's own data (never from invented defaults)."""
from decimal import Decimal

from django.db.models import Q

from apps.materials.models import Material


def catalog_board_prices(user) -> dict[str, float]:
    """`"KIND thickness"` -> price per m2, from materials that have a sheet price. A user's own material wins over a system one."""
    out: dict[str, float] = {}
    rows = (Material.objects.filter(Q(is_system=True) | Q(owner=user), price_per_sheet__isnull=False)
            .exclude(sheet_length=0).exclude(sheet_width=0).order_by("-is_system", "id"))  # system first, user's own overrides
    for m in rows:
        area_m2 = Decimal(m.sheet_length) * Decimal(m.sheet_width) / Decimal(1_000_000)
        out[f"{m.kind} {float(m.thickness):g}"] = float(round(m.price_per_sheet / area_m2, 2))
    return out
