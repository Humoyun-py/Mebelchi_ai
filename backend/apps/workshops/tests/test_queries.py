"""Query-count guards: the number of SQL queries must not grow with the number of rows (no N+1)."""
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.core.tests.helpers import make_user
from apps.projects.models import Project
from apps.workshops.models import Order, Task

from .helpers import API, ORDERS, TASKS, WS, Scene, add_member, hours, make_order, make_task


def count(client, url, params=None):
    with CaptureQueriesContext(connection) as ctx:
        r = client.get(url, params or {})
    assert r.status_code == 200, (url, r.status_code, getattr(r, "data", None))
    return len(ctx), r


class QueryCountTests(TestCase):
    def setUp(self):
        self.s = Scene()
        self.project = Project.objects.create(owner=self.s.owner, name="P")

    def grow(self, n):
        for i in range(n):
            o = make_order(self.s.ws, self.s.owner, title=f"Order {i}", assigned_employee=self.s.m_emp1.pk if i % 2 else self.s.m_emp2.pk,
                           related_project=self.project.pk, total_price="100")
            make_task(self.s.owner, o, assigned_to=self.s.m_emp1.pk if i % 3 else self.s.m_emp2.pk, deadline=hours(10).isoformat())

    def assert_constant(self, client, url, params=None, ceiling=12):
        self.grow(2)
        small, r1 = count(client, url, params)
        self.grow(12)
        big, r2 = count(client, url, params)
        self.assertEqual(small, big, f"{url}: {small} queries for few rows, {big} for many (N+1)")
        self.assertLessEqual(big, ceiling, url)
        return r2

    def test_order_list_owner(self):
        r = self.assert_constant(self.s.c_owner, ORDERS, {"page_size": 50})
        self.assertEqual(r.data["count"], 14)

    def test_order_list_employee(self):
        self.assert_constant(self.s.c_emp1, ORDERS, {"page_size": 50})

    def test_task_list_owner_and_employee(self):
        self.assert_constant(self.s.c_owner, TASKS, {"page_size": 50})
        self.assert_constant(self.s.c_emp1, TASKS, {"page_size": 50})

    def test_filtered_and_searched_lists_stay_flat(self):
        self.assert_constant(self.s.c_owner, ORDERS, {"page_size": 50, "status": "new", "search": "Order", "ordering": "-deadline"})
        self.assert_constant(self.s.c_owner, TASKS, {"page_size": 50, "overdue": "false", "mine": "false", "ordering": "deadline"})

    def test_order_detail_with_long_history_and_many_tasks(self):
        o = make_order(self.s.ws, self.s.owner, total_price="10")
        for st in ("confirmed", "in_production", "ready"):
            self.s.c_owner.patch(f"{ORDERS}{o.pk}/", {"status": st}, format="json")
        a, _ = count(self.s.c_owner, f"{ORDERS}{o.pk}/")
        for i in range(15):
            make_task(self.s.owner, Order.objects.get(pk=o.pk), assigned_to=self.s.m_emp1.pk)
        b, r = count(self.s.c_owner, f"{ORDERS}{o.pk}/")
        self.assertEqual((a, r.data["tasks_count"]), (b, 15))
        self.assertEqual(len(r.data["status_history"]), 4)

    def test_task_detail_with_long_history(self):
        o = make_order(self.s.ws, self.s.owner)
        t = make_task(self.s.owner, o, assigned_to=self.s.m_emp1.pk)
        a, _ = count(self.s.c_owner, f"{TASKS}{t.pk}/")
        for st in ("in_progress", "review", "in_progress", "review"):
            self.s.c_emp1.patch(f"{TASKS}{t.pk}/", {"status": st}, format="json")
        b, r = count(self.s.c_owner, f"{TASKS}{t.pk}/")
        self.assertEqual(a, b)
        self.assertEqual(len(r.data["status_history"]), 5)

    def test_workshop_and_member_lists(self):
        c = self.s.c_owner
        base_ws, _ = count(c, WS)
        base_m, _ = count(c, f"{WS}{self.s.ws.pk}/members/")
        for i in range(10):
            add_member(self.s.ws, make_user(f"extra{i}@x.com", "maker"))
        from .helpers import make_workshop
        for i in range(5):
            make_workshop(self.s.owner, f"More {i}")
        self.assertEqual(count(c, WS)[0], base_ws)
        self.assertEqual(count(c, f"{WS}{self.s.ws.pk}/members/")[0], base_m)
        self.assertEqual(count(c, f"{WS}{self.s.ws.pk}/members/")[1].data["count"], 13)

    def test_invitation_list(self):
        u = make_user("invitee@x.com", "maker")
        from .helpers import make_workshop
        base = None
        for i in range(2):
            ws = make_workshop(self.s.owner, f"Inv {i}")
            add_member(ws, u, status="invited")
        from apps.core.tests.helpers import client_for
        c = client_for(u)
        base, _ = count(c, API + "workshop-invitations/")
        for i in range(8):
            add_member(make_workshop(self.s.owner, f"Inv more {i}"), u, status="invited")
        n, r = count(c, API + "workshop-invitations/")
        self.assertEqual((n, r.data["count"]), (base, 10))


class PaginationTests(TestCase):
    def test_pages_are_bounded_and_complete(self):
        s = Scene()
        for i in range(30):
            make_order(s.ws, s.owner, title=f"O{i:02d}")
        r = s.c_owner.get(ORDERS)
        self.assertEqual((r.data["count"], len(r.data["results"])), (30, 24))   # default page size
        seen = {o["id"] for o in r.data["results"]} | {o["id"] for o in s.c_owner.get(ORDERS, {"page": 2}).data["results"]}
        self.assertEqual(len(seen), 30)                                          # no row lost or repeated across pages
        self.assertEqual(len(s.c_owner.get(ORDERS, {"page_size": 100}).data["results"]), 30)
        self.assertEqual(len(s.c_owner.get(ORDERS, {"page_size": 5}).data["results"]), 5)

    def test_page_boundaries_are_stable_when_sorting_by_a_tied_value(self):
        s = Scene()
        for i in range(12):
            make_order(s.ws, s.owner, title=f"Same {i}", deadline=None)
        a = [o["id"] for o in s.c_owner.get(ORDERS, {"ordering": "deadline", "page_size": 5, "page": 1}).data["results"]]
        b = [o["id"] for o in s.c_owner.get(ORDERS, {"ordering": "deadline", "page_size": 5, "page": 2}).data["results"]]
        c = [o["id"] for o in s.c_owner.get(ORDERS, {"ordering": "deadline", "page_size": 5, "page": 3}).data["results"]]
        self.assertEqual(len(set(a + b + c)), 12)
