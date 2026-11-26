"""Prices for marketplace offers.

Only prices somebody entered are used: the workshop's own `price_list` (board, edge tape, hardware, labour, markup, in the calculation engine's
PriceList format), a catalogue item's fixed `price`, the workshop's transport rate and assembly percentage. Nothing is looked up on the internet and
nothing is guessed: a workshop whose price list does not cover the furniture (some line has no price) gets NO quote and is left out of the ranking.

Pure functions over plain data (no requests); `quote_for_workshop` reads the workshop row it is given.
"""
from __future__ import annotations

from decimal import Decimal

from apps.calculations import engine
from apps.finance.services import money

DEFAULT_CURRENCY = "USD"
MAX_QUANTITY = 50


class NoQuote(Exception):
    """The workshop cannot price this furniture. `reason` is shown to the person asking (never an invented number)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def spec_from_item(item) -> dict:
    return {**item.defaults}


def quote_for_workshop(ws, spec: dict, quantity: int = 1, distance_km: float | None = None, catalog_item=None) -> dict:
    """Returns {"currency", "unit_price", "total", "lines", "source", "notes"}; raises NoQuote."""
    if not 1 <= quantity <= MAX_QUANTITY:
        raise NoQuote(f"quantity must be between 1 and {MAX_QUANTITY}")
    notes: list[str] = []
    if catalog_item is not None and catalog_item.workshop_id == ws.pk and catalog_item.price is not None:
        unit, currency, source, lines = Decimal(catalog_item.price), catalog_item.currency, "catalog", [{"item": catalog_item.name, "amount": str(catalog_item.price)}]
    else:
        if catalog_item is not None and catalog_item.workshop_id not in (None, ws.pk):
            raise NoQuote("this catalogue item belongs to another workshop")
        if not ws.price_list:
            raise NoQuote("the workshop has not entered a price list")
        try:
            pl = engine.parse_prices(ws.price_list)
            calc = engine.calculate(spec)
        except engine.EngineValidationError as e:
            raise NoQuote("; ".join(f"{k}: {m}" for k, m in e.errors.items()))
        est = engine.price_estimate(calc, pl)
        if not est["complete"]:
            raise NoQuote("the workshop's price list does not cover: " + ", ".join(est["missing"][:4]))
        unit, currency, source = money(est["total_price"]), pl.currency or DEFAULT_CURRENCY, "workshop_price_list"
        lines = [{"item": l["item"], "category": l["category"], "amount": str(l["amount"])} for l in est["lines"]]
        if ws.assembly_percent and ws.assembly_percent > 0:
            fee = money(unit * ws.assembly_percent / 100)
            unit += fee
            lines.append({"item": f"Assembly ({ws.assembly_percent}%)", "category": "assembly", "amount": str(fee)})
    total = money(unit * quantity)
    if ws.transport_per_km is not None and distance_km is not None:
        fee = money(Decimal(str(round(distance_km, 1))) * ws.transport_per_km)
        total += fee
        lines.append({"item": f"Transport (~{distance_km:.0f} km)", "category": "transport", "amount": str(fee)})
    elif ws.transport_per_km is not None:
        notes.append("Transport is not included: the distance is unknown (no delivery location given).")
    return {"currency": currency, "unit_price": str(money(unit)), "quantity": quantity, "total": str(total), "lines": lines, "source": source, "notes": notes,
            "basis": "Built from the workshop's own price list. An estimate for professional review, not a binding quotation."}


def tiers(totals: list[Decimal]) -> dict | None:
    """Minimum / average / premium over the quotes actually received. With no quotes there are no tiers."""
    if not totals:
        return None
    return {"min": str(money(min(totals))), "average": str(money(sum(totals) / len(totals))), "premium": str(money(max(totals))), "quotes": len(totals)}


def tier_of(total: Decimal, totals: list[Decimal]) -> str:
    lo, hi = min(totals), max(totals)
    if lo == hi:
        return "average"
    return "min" if total == lo else "premium" if total == hi else "average"
