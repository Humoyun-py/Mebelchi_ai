"""Customer side of the marketplace: choose a workshop, place the order, follow it, cancel, re-route a rejected order, rate the workshop.

Placing an order is the ONLY thing that reaches a workshop. Asking for matches creates nothing and tells nobody. The price is always recomputed on
the server from the workshop's own price list at the moment of placing: a price sent by the client is ignored."""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Avg, Count
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.audit.services import save_with_event
from apps.finance import services as finance
from apps.furniture import services as catalog
from apps.furniture.models import FurnitureTemplate
from apps.notifications.services import notify
from apps.workshops import services as ws_services
from apps.workshops.models import Order, Workshop, WorkshopReview

from . import matching, pricing

O = Order
RESPONSE_HOURS = 24


def err(field, msg):
    return ValidationError({field: msg})


def parse_request(user, data: dict) -> dict:
    """Validates the furniture / location / budget part shared by `match` and `place`. Returns plain values."""
    if not isinstance(data, dict):
        raise err("request", "must be an object")
    item = None
    cat = data.get("catalog_item")
    if cat is not None:
        if isinstance(cat, bool) or not isinstance(cat, int):
            raise err("catalog_item", "must be an item id")
        item = catalog.visible(user).filter(pk=cat, is_available=True).first()
        if item is None:
            raise err("catalog_item", "This catalogue item does not exist or is not available.")
        spec, category = catalog.clean_defaults(item.defaults), item.category
    else:
        f = data.get("furniture")
        if not isinstance(f, dict):
            raise err("furniture", "send `catalog_item` (an id) or `furniture` with category, width, height and depth")
        category = f.get("category")
        if category not in catalog.CATEGORY_SLUGS:
            raise err("furniture.category", f"must be one of: {', '.join(sorted(catalog.CATEGORY_SLUGS))}")
        spec = catalog.clean_defaults({k: f[k] for k in catalog.SIZE_KEYS if k in f})
    qty = data.get("quantity", 1)
    if isinstance(qty, bool) or not isinstance(qty, int) or not 1 <= qty <= pricing.MAX_QUANTITY:
        raise err("quantity", f"must be a whole number from 1 to {pricing.MAX_QUANTITY}")
    loc = data.get("customer_location")
    location = None
    if loc is not None:
        try:
            lat, lng = float(loc["latitude"]), float(loc["longitude"])
        except (TypeError, KeyError, ValueError):
            raise err("customer_location", "send {latitude, longitude}")
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise err("customer_location", "latitude must be -90..90 and longitude -180..180")
        location = (lat, lng)
    budget = data.get("budget")
    if budget is not None:
        try:
            budget = Decimal(str(budget))
        except Exception:  # noqa: BLE001
            raise err("budget", "must be a number")
        if budget <= 0:
            raise err("budget", "must be greater than zero")
    days = data.get("deadline_days")
    if days is not None and (isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 730):
        raise err("deadline_days", "must be a whole number of days from 1 to 730")
    excl = data.get("exclude_workshops", [])
    if not isinstance(excl, list) or any(isinstance(x, bool) or not isinstance(x, int) for x in excl):
        raise err("exclude_workshops", "must be a list of workshop ids")
    limit = data.get("limit", 3)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= matching.MAX_OPTIONS:
        raise err("limit", f"must be 1..{matching.MAX_OPTIONS}")
    return {"category": category, "spec": spec, "quantity": qty, "catalog_item": item, "location": location, "budget": budget, "deadline_days": days,
            "currency": data.get("currency") or None, "exclude": excl, "limit": limit}


def find_matches(user, data: dict) -> dict:
    p = parse_request(user, data)
    return matching.match(category=p["category"], spec=p["spec"], quantity=p["quantity"], catalog_item=p["catalog_item"], location=p["location"],
                          budget=p["budget"], deadline_days=p["deadline_days"], currency=p["currency"], limit=p["limit"], exclude=p["exclude"])


def place_order(user, data: dict, *, rerouted_from: Order | None = None) -> Order:
    ws_id = data.get("workshop") if isinstance(data, dict) else None
    if isinstance(ws_id, bool) or not isinstance(ws_id, int):
        raise err("workshop", "choose one of the offered workshops")
    p = parse_request(user, data)
    with transaction.atomic():
        ws = Workshop.objects.select_for_update().select_related("owner").filter(pk=ws_id).first()
        if ws is None:
            raise err("workshop", "This workshop does not exist.")
        res = matching.match(category=p["category"], spec=p["spec"], quantity=p["quantity"], catalog_item=p["catalog_item"], location=p["location"],
                             budget=None, deadline_days=p["deadline_days"], currency=p["currency"], limit=1, only=[ws.pk])
        if not res["options"]:
            reason = next((e["reason"] for e in res["excluded"] if e["workshop"] == ws.pk), "is not available for new orders")
            raise err("workshop", f"This workshop {reason}.")
        opt = res["options"][0]
        q = opt["quote"]
        total = Decimal(q["total"])
        pct = finance.commission_percent()
        commission, payable = finance.split(total, pct)
        name = (data.get("customer_name") or user.full_name or user.email).strip()[:160]
        phone = (data.get("customer_phone") or user.phone or "").strip()[:32]
        item = p["catalog_item"]
        title = (item.name if item else f"Custom {p['category'].replace('_', ' ')}")[:200]
        order = Order(workshop=ws, order_number=ws_services.next_order_number(ws), source=O.Source.MARKETPLACE, status=O.Status.PENDING, created_by=user,
                      customer_user=user, customer_name=name, customer_phone=phone, customer_email=user.email, customer_address=str(data.get("customer_address", ""))[:255],
                      title=title, description=str(data.get("notes", ""))[:2000], catalog_item=item, price_tier=opt["price_tier"], total_price=total,
                      commission_percent=pct, commission_amount=commission, workshop_amount=payable, delivery_distance_km=opt["distance_km"],
                      deadline=timezone.localdate() + datetime.timedelta(days=opt["lead_time_days"]), rerouted_from=rerouted_from,
                      customer_latitude=p["location"][0] if p["location"] else None, customer_longitude=p["location"][1] if p["location"] else None,
                      quote={"spec": p["spec"], "category": p["category"], "quantity": p["quantity"], "currency": q["currency"], "lines": q["lines"],
                             "source": q["source"], "notes": q["notes"], "budget": str(p["budget"]) if p["budget"] else None, "deadline_days": p["deadline_days"]})
        save_with_event(order, "order.placed")
        ws_services._log_order(order, "", user, "Placed through the marketplace")
        notify(ws.owner, f"New order {order.order_number}", f"{title}, {q['currency']} {q['total']}. Please accept or reject it within {RESPONSE_HOURS} hours.", "info")
        notify(user, f"Order {order.order_number}", f"Your order was sent to {ws.name}. They have {RESPONSE_HOURS} hours to answer; we will tell you as soon as they do.")
        return order


def my_orders(user):
    return Order.objects.filter(customer_user=user, source=O.Source.MARKETPLACE).select_related("workshop", "review", "rerouted_from").prefetch_related("payments")


def get_order(user, pk) -> Order:
    o = my_orders(user).filter(pk=pk).first()
    if o is None:
        raise NotFound()
    return o


def cancel(user, pk) -> Order:
    with transaction.atomic():
        o = Order.objects.select_for_update(of=("self",)).filter(pk=pk, customer_user=user, source=O.Source.MARKETPLACE).select_related("workshop__owner").first()
        if o is None:
            raise NotFound()
        if o.status not in (O.Status.PENDING, O.Status.CONFIRMED):
            raise err("status", f"An order that is {o.status} can no longer be cancelled by the customer.")
        if o.paid_amount > 0:
            raise err("status", "This order has a payment on record; ask the platform to cancel and refund it.")
        old = o.status
        o.status, o.responded_at = O.Status.CANCELLED, o.responded_at or timezone.now()
        save_with_event(o, "order.status_changed")
        ws_services._log_order(o, old, user, "Cancelled by the customer")
        ws_services._cancel_open_tasks(o, user)
        notify(o.workshop.owner, f"Order {o.order_number}", "The customer cancelled this order.", "warning")
        return o


def alternatives(user, pk) -> dict:
    o = get_order(user, pk)
    if o.status != O.Status.REJECTED:
        raise err("status", "Alternatives are offered for rejected orders only.")
    q = o.quote
    tried = set(Order.objects.filter(Q_chain(o)).values_list("workshop_id", flat=True)) | {o.workshop_id}
    return matching.match(category=q["category"], spec=q["spec"], quantity=q["quantity"], catalog_item=o.catalog_item,
                          location=(float(o.customer_latitude), float(o.customer_longitude)) if o.customer_latitude is not None else None,
                          budget=Decimal(q["budget"]) if q.get("budget") else None, deadline_days=q.get("deadline_days"), currency=q["currency"], exclude=tried)


def Q_chain(o: Order):
    """All orders of the same re-routing chain (so a workshop that already refused is never offered again)."""
    from django.db.models import Q
    root = o
    while root.rerouted_from_id:
        root = root.rerouted_from
    ids, frontier = {root.pk}, [root.pk]
    while frontier:
        nxt = list(Order.objects.filter(rerouted_from_id__in=frontier).values_list("pk", flat=True))
        frontier = [i for i in nxt if i not in ids]
        ids.update(frontier)
    return Q(pk__in=ids)


def reassign(user, pk, workshop_id) -> Order:
    with transaction.atomic():
        o = Order.objects.select_for_update(of=("self",)).filter(pk=pk, customer_user=user, source=O.Source.MARKETPLACE).select_related("rerouted_from").first()
        if o is None:
            raise NotFound()
        if o.status != O.Status.REJECTED:
            raise err("status", "Only a rejected order can be sent to another workshop.")
        if o.rerouted_to.exists():
            raise err("status", "This order was already sent to another workshop.")
        tried = set(Order.objects.filter(Q_chain(o)).values_list("workshop_id", flat=True))
        if workshop_id in tried:
            raise err("workshop", "This workshop already handled or refused this order.")
        q = o.quote
        data = {"workshop": workshop_id, "furniture": {"category": q["category"], **q["spec"]} if not o.catalog_item_id else None,
                "catalog_item": o.catalog_item_id, "quantity": q["quantity"], "budget": q.get("budget"), "deadline_days": q.get("deadline_days"),
                "currency": q["currency"], "customer_name": o.customer_name, "customer_phone": o.customer_phone, "customer_address": o.customer_address,
                "notes": o.description}
        if o.customer_latitude is not None:
            data["customer_location"] = {"latitude": float(o.customer_latitude), "longitude": float(o.customer_longitude)}
        if o.catalog_item_id:
            data.pop("furniture")
        return place_order(user, data, rerouted_from=o)


def review(user, pk, stars, comment="") -> WorkshopReview:
    if isinstance(stars, bool) or not isinstance(stars, int) or not 1 <= stars <= 5:
        raise err("stars", "must be a whole number from 1 to 5")
    with transaction.atomic():
        o = Order.objects.select_for_update(of=("self",)).filter(pk=pk, customer_user=user, source=O.Source.MARKETPLACE).first()
        if o is None:
            raise NotFound()
        if o.status != O.Status.DELIVERED:
            raise err("status", "You can rate a workshop after the order is completed.")
        if WorkshopReview.objects.filter(order=o).exists():
            raise err("status", "You already rated this order.")
        r = WorkshopReview.objects.create(order=o, workshop_id=o.workshop_id, customer=user, stars=stars, comment=str(comment or "")[:1000])
        ws = Workshop.objects.select_for_update().get(pk=o.workshop_id)
        agg = WorkshopReview.objects.filter(workshop=ws).aggregate(n=Count("id"), avg=Avg("stars"))
        Workshop.objects.filter(pk=ws.pk).update(rating_count=agg["n"], rating_avg=Decimal(str(round(agg["avg"], 2))))
        return r
