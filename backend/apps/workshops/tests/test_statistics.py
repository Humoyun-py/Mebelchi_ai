from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.core.tests.helpers import client_for, make_user
from apps.workshops.models import Order, Task

from .helpers import WS, Scene, add_member, hours, make_order, make_task, make_workshop


def stats_url(ws):
    return f"{WS}{ws.pk}/statistics/"


class StatisticsTests(TestCase):
    def setUp(self):
        s = self.s = Scene()
        add_member(s.ws, make_user("inv@x.com", "maker"), status="invited")
        add_member(s.ws, make_user("rem@x.com", "maker"), status="removed")

        def order(total, paid, status="new", pay=None):
            o = make_order(s.ws, s.owner, total_price=str(total), paid_amount=str(paid))
            upd = {"status": status}
            if pay:
                upd["payment_status"] = pay
            Order.objects.filter(pk=o.pk).update(**upd)
            return o

        self.o1 = order(1000, 0, "new")
        self.o2 = order(2000, 500, "confirmed")
        self.o3 = order(3000, 3000, "in_production")
        self.o4 = order(4000, 4000, "delivered")
        self.o5 = order(800, 100, "cancelled")
        self.o6 = order(600, 600, "ready", pay="refunded")
        # noise in another workshop must not leak into these numbers
        make_order(s.wsb, s.owner_b, total_price="999999", paid_amount="999999")
        make_task(s.owner_b, ws=s.wsb)

        def task(status, deadline=None, order=None):
            t = make_task(s.owner, order, ws=None if order else s.ws)
            Task.objects.filter(pk=t.pk).update(status=status, deadline=deadline)

        task("pending", order=self.o1)
        task("in_progress", hours(-3), order=self.o3)     # overdue
        task("review", hours(-1), order=self.o3)           # overdue
        task("completed", hours(-50), order=self.o3)       # late, but finished: not overdue
        task("cancelled", hours(-9))                        # not overdue
        task("pending", hours(30))                          # future

    def test_figures_come_from_the_records(self):
        d = self.s.c_owner.get(stats_url(self.s.ws)).data
        self.assertEqual(d["orders"], {"total": 6, "new": 1, "confirmed": 1, "in_production": 1, "ready": 1, "delivered": 1, "completed": 1, "cancelled": 1})
        self.assertEqual(d["tasks"], {"total": 6, "pending": 2, "in_progress": 1, "review": 1, "completed": 1, "cancelled": 1, "overdue": 2})
        self.assertEqual(d["employees"], {"total": 3, "active": 2, "invited": 1})      # owner not counted; removed not counted
        m = d["money"]
        self.assertEqual(Decimal(str(m["total_order_value"])), Decimal("10600"))      # all but the cancelled order
        self.assertEqual(Decimal(str(m["paid_amount"])), Decimal("7600"))              # refunded order excluded
        self.assertEqual(Decimal(str(m["outstanding_amount"])), Decimal("2500"))       # 1000 + 1500 over live, unrefunded orders
        self.assertEqual(d["workshop"], self.s.ws.pk)

    def test_the_numbers_follow_the_data(self):
        c = self.s.c_owner
        before = c.get(stats_url(self.s.ws)).data
        c.patch(f"/api/v1/orders/{self.o1.pk}/", {"paid_amount": "1000"}, format="json")
        c.patch(f"/api/v1/orders/{self.o2.pk}/", {"status": "cancelled"}, format="json")
        after = c.get(stats_url(self.s.ws)).data
        self.assertEqual(after["orders"]["cancelled"], before["orders"]["cancelled"] + 1)
        self.assertEqual(after["orders"]["confirmed"], 0)
        self.assertEqual(Decimal(str(after["money"]["total_order_value"])), Decimal("8600"))   # 10600 - 2000
        self.assertEqual(Decimal(str(after["money"]["outstanding_amount"])), Decimal("0"))     # o1 now fully paid, o2 cancelled

    def test_each_workshop_only_counts_its_own_records(self):
        d = self.s.c_owner_b.get(stats_url(self.s.wsb)).data
        self.assertEqual((d["orders"]["total"], d["tasks"]["total"], d["employees"]["total"]), (1, 1, 0))
        self.assertEqual(Decimal(str(d["money"]["total_order_value"])), Decimal("999999"))

    def test_an_empty_workshop_reports_zeros_not_nulls(self):
        ws = make_workshop(self.s.owner, "Empty")
        d = self.s.c_owner.get(stats_url(ws)).data
        self.assertEqual(d["orders"]["total"], 0)
        self.assertEqual(d["tasks"]["overdue"], 0)
        self.assertEqual([Decimal(str(d["money"][k])) for k in ("total_order_value", "paid_amount", "outstanding_amount")], [0, 0, 0])

    def test_only_the_owner_can_read_statistics(self):
        self.assertEqual(self.s.c_emp1.get(stats_url(self.s.ws)).status_code, 403)
        self.assertEqual(self.s.c_stranger.get(stats_url(self.s.ws)).status_code, 404)
        self.assertEqual(self.s.c_owner_b.get(stats_url(self.s.ws)).status_code, 404)
        self.assertEqual(client_for().get(stats_url(self.s.ws)).status_code, 401)

    def test_it_is_read_only(self):
        self.assertEqual(self.s.c_owner.post(stats_url(self.s.ws), {}, format="json").status_code, 405)

    def test_statistics_use_a_fixed_number_of_queries(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as small:
            self.s.c_owner.get(stats_url(self.s.ws))
        for i in range(25):
            o = make_order(self.s.ws, self.s.owner, total_price="10")
            make_task(self.s.owner, o)
        with CaptureQueriesContext(connection) as big:
            self.s.c_owner.get(stats_url(self.s.ws))
        self.assertEqual(len(small), len(big))
        self.assertLessEqual(len(big), 8)
