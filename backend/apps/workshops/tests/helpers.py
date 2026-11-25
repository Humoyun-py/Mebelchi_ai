import datetime

from django.utils import timezone

from apps.core.tests.helpers import client_for, make_user
from apps.workshops.models import Order, Task, Workshop, WorkshopMember

API = "/api/v1/"
WS = API + "workshops/"
ORDERS = API + "orders/"
TASKS = API + "tasks/"


def days(n):
    return timezone.localdate() + datetime.timedelta(days=n)


def hours(n):
    return timezone.now() + datetime.timedelta(hours=n)


def make_workshop(owner, name="Alpha Workshop"):
    """Creates a workshop through the API (so the real service path is used)."""
    r = client_for(owner).post(WS, {"name": name}, format="json")
    assert r.status_code == 201, r.data
    return Workshop.objects.get(pk=r.data["id"])


def add_member(ws, user, status=WorkshopMember.Status.ACTIVE, role=WorkshopMember.Role.EMPLOYEE):
    return WorkshopMember.objects.create(workshop=ws, user=user, role=role, status=status,
                                         joined_at=timezone.now() if status == "active" else None)


def member_of(ws, user):
    return WorkshopMember.objects.get(workshop=ws, user=user)


def make_order(ws, owner, **kw):
    r = client_for(owner).post(ORDERS, {"workshop": ws.pk, "title": kw.pop("title", "Kitchen"), "customer_name": kw.pop("customer_name", "Ali Valiyev"), **kw},
                               format="json")
    assert r.status_code == 201, r.data
    return Order.objects.get(pk=r.data["id"])


def make_task(owner, order=None, ws=None, **kw):
    body = {"title": kw.pop("title", "Cut panels"), **kw}
    if order is not None:
        body["order"] = order.pk
    if ws is not None:
        body["workshop"] = ws.pk
    r = client_for(owner).post(TASKS, body, format="json")
    assert r.status_code == 201, r.data
    return Task.objects.get(pk=r.data["id"])


class Scene:
    """owner + two employees in workshop A; a stranger and a second workshop B with its own owner."""

    def __init__(self):
        self.owner = make_user("owner@a.com", "maker")
        self.emp1 = make_user("emp1@a.com", "maker")
        self.emp2 = make_user("emp2@a.com", "maker")
        self.stranger = make_user("stranger@x.com", "maker")
        self.owner_b = make_user("owner@b.com", "maker")
        self.ws = make_workshop(self.owner, "Alpha Workshop")
        self.wsb = make_workshop(self.owner_b, "Beta Workshop")
        self.m_emp1 = add_member(self.ws, self.emp1)
        self.m_emp2 = add_member(self.ws, self.emp2)
        self.c_owner, self.c_emp1, self.c_emp2 = client_for(self.owner), client_for(self.emp1), client_for(self.emp2)
        self.c_stranger, self.c_owner_b = client_for(self.stranger), client_for(self.owner_b)
