"""Workshop matching. Deterministic and explainable: the same request over the same data always gives the same ranking, and every option
carries the numbers it was ranked by. No AI is involved (prices, distance and capacity must never depend on one).

Hard filters (a workshop that fails one is listed under `excluded` with the reason, not silently dropped):
  active and accepting orders, makes this category, has a complete quote, same currency, delivers to the customer, within the deadline,
  has free capacity.
Ranking: weighted score 0..100 from price, distance, rating, lead time and current load (weights below). Budget and unknown data are flagged.
"""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Q

from apps.finance.services import money
from apps.furniture.models import FurnitureTemplate
from apps.workshops.models import Order, Workshop

from . import pricing
from .geo import haversine_km

WEIGHTS = {"price": 35, "distance": 20, "rating": 20, "lead_time": 15, "load": 10}
BUSY = [Order.Status.CONFIRMED, Order.Status.IN_PRODUCTION, Order.Status.QUALITY_CHECK, Order.Status.READY, Order.Status.DELIVERY]
MAX_OPTIONS = 10


def _rel(value, lo, hi):
    """1.0 for the best (lowest) value, 0.0 for the worst; 1.0 when everybody is equal."""
    return 1.0 if hi == lo else 1.0 - (value - lo) / (hi - lo)


def candidates(exclude=(), only=None):
    qs = Workshop.objects.filter(pk__in=list(only)) if only is not None else Workshop.objects.all()
    return (qs.filter(status=Workshop.Status.ACTIVE, is_accepting_orders=True).exclude(pk__in=list(exclude))
            .annotate(active_orders=Count("orders", filter=Q(orders__status__in=BUSY))).select_related("owner"))


def portfolio(ws: Workshop, limit: int = 4) -> list[dict]:
    from apps.furniture.views import IMAGE_KIND
    from apps.core.signing import sign_file
    items = FurnitureTemplate.objects.filter(workshop=ws, is_active=True, status=FurnitureTemplate.Status.APPROVED).prefetch_related("images")[:limit]
    out = []
    for t in items:
        img = next((i for i in t.images.all() if i.view == "front"), None) or next(iter(t.images.all()), None)
        out.append({"id": t.pk, "name": t.name, "image_url": f"/api/v1/furniture/images/{img.pk}/file/?sig={sign_file(IMAGE_KIND, img.pk)}" if img else None})
    return out


def match(*, category: str | None, spec: dict, quantity: int = 1, catalog_item=None, location: tuple | None = None, budget: Decimal | None = None,
          deadline_days: int | None = None, currency: str | None = None, limit: int = 3, exclude=(), only=None) -> dict:
    limit = max(1, min(limit, MAX_OPTIONS))
    excluded: list[dict] = []
    rows = []
    for ws in candidates(exclude, only):
        why = None
        if category and ws.categories and category not in ws.categories:
            why = "does not make this kind of furniture"
        elif ws.active_orders >= ws.max_active_orders:
            why = "has no free capacity right now"
        dist = None
        if why is None and location and ws.latitude is not None:
            dist = haversine_km(location[0], location[1], ws.latitude, ws.longitude)
            if ws.delivery_radius_km is not None and dist > ws.delivery_radius_km:
                why = f"does not deliver that far (~{dist:.0f} km, limit {ws.delivery_radius_km} km)"
        lead = (catalog_item.lead_time_days if catalog_item is not None and catalog_item.workshop_id == ws.pk and catalog_item.lead_time_days else ws.lead_time_days)
        if why is None and deadline_days is not None and lead > deadline_days:
            why = f"needs about {lead} days, longer than the {deadline_days} you asked for"
        q = None
        if why is None:
            try:
                q = pricing.quote_for_workshop(ws, spec, quantity, dist, catalog_item)
            except pricing.NoQuote as e:
                why = f"cannot price this: {e.reason}"
        if why:
            excluded.append({"workshop": ws.pk, "name": ws.name, "reason": why})
        else:
            rows.append({"ws": ws, "quote": q, "distance": dist, "lead": lead})
    cur = currency or (max({r["quote"]["currency"] for r in rows}, key=lambda c: sum(r["quote"]["currency"] == c for r in rows)) if rows else None)
    kept = []
    for r in rows:
        if r["quote"]["currency"] != cur:
            excluded.append({"workshop": r["ws"].pk, "name": r["ws"].name, "reason": f"quotes in {r['quote']['currency']}, not {cur}"})
        else:
            kept.append(r)
    if not kept:
        return {"options": [], "tiers": None, "currency": cur, "excluded": excluded, "weights": WEIGHTS}
    totals = [Decimal(r["quote"]["total"]) for r in kept]
    plo, phi = float(min(totals)), float(max(totals))
    dists = [r["distance"] for r in kept if r["distance"] is not None]
    dlo, dhi = (min(dists), max(dists)) if dists else (0.0, 0.0)
    leads = [r["lead"] for r in kept]
    for r in kept:
        ws, total = r["ws"], Decimal(r["quote"]["total"])
        parts = {"price": _rel(float(total), plo, phi),
                 "distance": 0.5 if r["distance"] is None else _rel(r["distance"], dlo, dhi),
                 "rating": float(ws.rating_avg) / 5 if ws.rating_count else 0.5,
                 "lead_time": _rel(r["lead"], min(leads), max(leads)),
                 "load": 1.0 - ws.active_orders / ws.max_active_orders}
        r["score"] = round(sum(WEIGHTS[k] * v for k, v in parts.items()), 2)
        r["parts"] = {k: round(v, 3) for k, v in parts.items()}
        r["over_budget"] = budget is not None and total > budget
        if r["over_budget"]:
            r["score"] = round(r["score"] * 0.6, 2)                        # still shown (so the person sees the real prices), clearly behind
    kept.sort(key=lambda r: (-r["score"], Decimal(r["quote"]["total"]), r["ws"].pk))
    options = []
    for r in kept[:limit]:
        ws, q = r["ws"], r["quote"]
        flags = []
        if r["distance"] is None:
            flags.append("distance_unknown")
        if not ws.rating_count:
            flags.append("no_ratings_yet")
        if r["over_budget"]:
            flags.append("over_budget")
        options.append({"workshop": ws.pk, "name": ws.name, "city": ws.city, "price": q["total"], "currency": q["currency"], "price_tier": pricing.tier_of(Decimal(q["total"]), totals),
                        "lead_time_days": r["lead"], "distance_km": None if r["distance"] is None else round(r["distance"], 1),
                        "rating": float(ws.rating_avg) if ws.rating_count else None, "rating_count": ws.rating_count,
                        "load": f"{ws.active_orders}/{ws.max_active_orders}", "score": r["score"], "score_parts": r["parts"], "flags": flags,
                        "quote": q, "portfolio": portfolio(ws)})
    return {"options": options, "tiers": pricing.tiers(totals), "currency": cur, "excluded": excluded, "weights": WEIGHTS,
            "note": f"{len(options)} of {len(kept)} matching workshops shown. Prices are estimates from each workshop's own price list; nothing is ordered until you choose one."}
