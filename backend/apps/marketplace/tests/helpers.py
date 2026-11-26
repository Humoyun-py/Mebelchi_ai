import copy
from decimal import Decimal

from apps.core.tests.helpers import client_for, make_user
from apps.workshops.models import Workshop
from apps.workshops.tests.helpers import make_workshop

FURN = {"category": "kitchen", "width": 900, "height": 720, "depth": 500, "thickness": 18, "shelves": 1, "doors": 2, "drawers": 0}
BASE_PRICES = {"currency": "USD", "board_price_per_m2": {"MDF 18": 20, "HDF 4": 8}, "edge_price_per_m": 0.5, "labor_per_m2": 10,
               "hardware_prices": {"Hinge": 2, "Handle": 3, "Shelf pin": 0.1, "Confirmat screw": 0.05, "Back panel fixing": 0.05}, "markup_pct": 20}


def prices(scale=1.0, **over):
    p = copy.deepcopy(BASE_PRICES)
    p["board_price_per_m2"] = {k: v * scale for k, v in p["board_price_per_m2"].items()}
    p.update(over)
    return p


def shop(name, email, *, scale=1.0, lat=41.3111, lng=69.2797, **fields):
    owner = make_user(email, "workshop")
    ws = make_workshop(owner, name)
    Workshop.objects.filter(pk=ws.pk).update(price_list=prices(scale), latitude=Decimal(str(lat)), longitude=Decimal(str(lng)), **fields)
    ws.refresh_from_db()
    return ws


def customer(email="cust@x.com"):
    u = make_user(email, "homeowner")
    return u, client_for(u)
