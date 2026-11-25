from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.core.tests.helpers import client_for, make_user
from apps.projects.models import Project
from apps.workshops.models import Order, OrderStatusChange, Task

from .helpers import API, ORDERS, WS, Scene, add_member, days, hours, make_order, make_task, make_workshop

BASE = {"title": "Kitchen set", "customer_name": "Ali Valiyev"}


def order_url(o):
    return f"{ORDERS}{o.pk}/"


class OrderCreationTests(TestCase):
    def setUp(self):
        self.s = Scene()

    def post(self, **kw):
        return self.s.c_owner.post(ORDERS, {"workshop": self.s.ws.pk, **BASE, **kw}, format="json")

    def test_owner_creates_an_order(self):
        r = self.post(customer_phone="+998901234567", customer_email="ali@x.com", customer_address="Tashkent", description="Oak",
                      total_price="5000000", paid_amount="1000000", start_date=str(days(1)), deadline=str(days(30)))
        self.assertEqual(r.status_code, 201, r.data)
        d = r.data
        self.assertEqual((d["status"], d["payment_status"], d["total_price"], d["paid_amount"], d["outstanding_amount"]),
                         ("new", "partially_paid", "5000000.00", "1000000.00", "4000000.00"))
        self.assertEqual(d["created_by"], self.s.owner.pk)
        o = Order.objects.get(pk=d["id"])
        self.assertEqual(o.workshop, self.s.ws)
        h = list(o.status_history.all())
        self.assertEqual([(x.from_status, x.to_status, x.changed_by) for x in h], [("", "new", self.s.owner)])

    def test_order_numbers_are_sequential_per_workshop_and_never_reused(self):
        a, b = self.post().data["order_number"], self.post().data["order_number"]
        pk = self.s.ws.pk
        self.assertEqual((a, b), (f"ORD-{pk:04d}-000001", f"ORD-{pk:04d}-000002"))
        Order.objects.get(order_number=b).delete()
        self.assertEqual(self.post().data["order_number"], f"ORD-{pk:04d}-000003")
        other = self.s.c_owner_b.post(ORDERS, {"workshop": self.s.wsb.pk, **BASE}, format="json").data["order_number"]
        self.assertEqual(other, f"ORD-{self.s.wsb.pk:04d}-000001")
        self.assertEqual(len({a, b, other}), 3)

    def test_order_number_is_unique_in_the_database(self):
        o = make_order(self.s.ws, self.s.owner)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Order.objects.create(workshop=self.s.ws, order_number=o.order_number, title="dup", customer_name="x")

    def test_order_number_and_status_cannot_be_forged(self):
        r = self.post(order_number="HACK-1", status="delivered", payment_status="paid", created_by=self.s.stranger.pk, completed_at="2020-01-01T00:00:00Z")
        o = Order.objects.get(pk=r.data["id"])
        self.assertEqual((o.status, o.payment_status, o.created_by, o.completed_at), ("new", "unpaid", self.s.owner, None))
        self.assertTrue(o.order_number.startswith("ORD-"))

    def test_only_the_owner_can_create(self):
        self.assertEqual(self.s.c_emp1.post(ORDERS, {"workshop": self.s.ws.pk, **BASE}, format="json").status_code, 403)
        self.assertEqual(client_for().post(ORDERS, {"workshop": self.s.ws.pk, **BASE}, format="json").status_code, 401)

    def test_workshop_is_required_and_foreign_workshops_look_nonexistent(self):
        self.assertEqual(self.s.c_owner.post(ORDERS, BASE, format="json").status_code, 400)
        foreign = self.s.c_owner.post(ORDERS, {"workshop": self.s.wsb.pk, **BASE}, format="json")
        missing = self.s.c_owner.post(ORDERS, {"workshop": 99999, **BASE}, format="json")
        self.assertEqual((foreign.status_code, missing.status_code), (400, 400))
        codes = lambda r: [e.code for e in r.data["error"]["fields"]["workshop"]]
        self.assertEqual(codes(foreign), codes(missing))  # no way to tell them apart
        self.assertEqual(Order.objects.filter(workshop=self.s.wsb).count(), 0)

    def test_validation(self):
        bad = [({"customer_name": ""}, "customer_name"), ({"title": ""}, "title"), ({"total_price": "-1"}, "total_price"),
               ({"total_price": "abc"}, "total_price"), ({"total_price": "1000", "paid_amount": "1001"}, "paid_amount"),
               ({"paid_amount": "5"}, "paid_amount"), ({"customer_email": "nope"}, "customer_email"),
               ({"total_price": "99999999999999"}, "total_price"),
               ({"start_date": str(days(10)), "deadline": str(days(5))}, "deadline"), ({"deadline": str(days(-1))}, "deadline")]
        for extra, field in bad:
            r = self.post(**extra)
            self.assertEqual(r.status_code, 400, (extra, r.data))
            self.assertIn(field, r.data["error"]["fields"], extra)
        self.assertEqual(Order.objects.count(), 0)

    def test_assigned_employee_must_be_an_active_member_of_the_same_workshop(self):
        invited = add_member(self.s.ws, make_user("inv@x.com", "maker"), status="invited")
        removed = add_member(self.s.ws, make_user("rem@x.com", "maker"), status="removed")
        other_ws_member = add_member(self.s.wsb, self.s.emp1)
        for m in (invited, removed):
            r = self.post(assigned_employee=m.pk)
            self.assertEqual(r.status_code, 400, r.data)
            self.assertIn("assigned_employee", r.data["error"]["fields"])
        r = self.post(assigned_employee=other_ws_member.pk)  # a member of workshop B: not visible to this owner
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.post(assigned_employee=self.s.m_emp1.pk).status_code, 201)

    def test_related_project_must_be_the_creators_own(self):
        mine = Project.objects.create(owner=self.s.owner, name="Kitchen design")
        theirs = Project.objects.create(owner=self.s.stranger, name="Private")
        ok = self.post(related_project=mine.pk)
        self.assertEqual((ok.status_code, ok.data["project"]), (201, {"id": mine.pk, "name": "Kitchen design"}))
        self.assertEqual(self.post(related_project=theirs.pk).status_code, 400)
        codes = lambda r: [e.code for e in r.data["error"]["fields"]["related_project"]]
        self.assertEqual(codes(self.post(related_project=99999)), codes(self.post(related_project=theirs.pk)))

    def test_deleting_the_project_keeps_the_order(self):
        p = Project.objects.create(owner=self.s.owner, name="P")
        o = Order.objects.get(pk=self.post(related_project=p.pk).data["id"])
        p.delete()
        o.refresh_from_db()
        self.assertIsNone(o.related_project)


class PaymentTests(TestCase):
    def setUp(self):
        self.s = Scene()
        self.o = make_order(self.s.ws, self.s.owner, total_price="1000")

    def patch(self, **kw):
        return self.s.c_owner.patch(order_url(self.o), kw, format="json")

    def test_payment_status_follows_the_paid_amount(self):
        self.assertEqual(self.o.payment_status, "unpaid")
        self.assertEqual(self.patch(paid_amount="300").data["payment_status"], "partially_paid")
        self.assertEqual(self.patch(paid_amount="1000").data["payment_status"], "paid")
        self.assertEqual(self.patch(paid_amount="0").data["payment_status"], "unpaid")
        self.assertEqual(self.patch(paid_amount="250.50").data["outstanding_amount"], "749.50")

    def test_cannot_overpay_or_shrink_the_price_below_what_was_paid(self):
        self.assertEqual(self.patch(paid_amount="1000.01").status_code, 400)
        self.patch(paid_amount="800")
        r = self.patch(total_price="500")
        self.assertEqual(r.status_code, 400)
        self.assertIn("total_price", r.data["error"]["fields"])
        self.assertEqual(self.patch(total_price="900").data["payment_status"], "partially_paid")

    def test_payment_status_cannot_be_set_to_a_wrong_value(self):
        r = self.patch(payment_status="paid")
        self.assertEqual(r.status_code, 400)
        self.assertIn("follows the paid amount", str(r.data))
        self.assertEqual(self.patch(payment_status="unpaid").status_code, 200)  # the derived value is accepted

    def test_refund_rules(self):
        self.assertEqual(self.patch(payment_status="refunded").status_code, 400)  # nothing was paid
        self.patch(paid_amount="1000")
        r = self.patch(payment_status="refunded")
        self.assertEqual((r.status_code, r.data["payment_status"], r.data["outstanding_amount"]), (200, "refunded", "0.00"))
        self.assertEqual(self.patch(paid_amount="0").status_code, 400)           # the record is closed
        self.assertEqual(self.patch(payment_status="paid").status_code, 400)
        self.assertEqual(self.patch(title="Renamed").status_code, 200)          # other fields stay editable
        self.o.refresh_from_db()
        self.assertEqual(self.o.paid_amount, Decimal("1000"))                    # the amount is kept as the historical record

    def test_database_rejects_inconsistent_money(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Order.objects.filter(pk=self.o.pk).update(paid_amount=Decimal("2000"))
        with self.assertRaises(IntegrityError), transaction.atomic():
            Order.objects.filter(pk=self.o.pk).update(total_price=Decimal("-1"), paid_amount=Decimal("0"))
        with self.assertRaises(IntegrityError), transaction.atomic():
            Order.objects.filter(pk=self.o.pk).update(start_date=days(5), deadline=days(1))


class OrderLifecycleTests(TestCase):
    def setUp(self):
        self.s = Scene()
        self.o = make_order(self.s.ws, self.s.owner, total_price="1000")

    def go(self, status, **kw):
        return self.s.c_owner.patch(order_url(self.o), {"status": status, **kw}, format="json")

    def test_the_normal_lifecycle_and_its_side_effects(self):
        self.assertEqual(self.go("confirmed", status_note="Deposit received").status_code, 200)
        r = self.go("in_production")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["start_date"], str(timezone.localdate()))     # production start defaults to today
        self.assertEqual(self.go("ready").status_code, 200)
        r = self.go("delivered")
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(r.data["completed_at"])
        hist = [(h["from_status"], h["to_status"]) for h in r.data["status_history"]]
        self.assertEqual(hist, [("", "new"), ("new", "confirmed"), ("confirmed", "in_production"), ("in_production", "ready"), ("ready", "delivered")])
        self.assertEqual(r.data["status_history"][1]["note"], "Deposit received")
        self.assertEqual(r.data["status_history"][1]["changed_by"]["id"], self.s.owner.pk)

    def test_existing_start_date_is_kept(self):
        self.s.c_owner.patch(order_url(self.o), {"start_date": str(days(3))}, format="json")
        self.go("confirmed")
        self.assertEqual(self.go("in_production").data["start_date"], str(days(3)))

    def test_invalid_transitions_are_rejected_and_explained(self):
        for bad in ("ready", "delivered", "in_production"):
            r = self.go(bad)
            self.assertEqual(r.status_code, 400, bad)
            self.assertIn("Allowed next statuses: cancelled, confirmed", r.data["error"]["fields"]["status"])
        self.assertEqual(self.go("nonsense").status_code, 400)
        self.o.refresh_from_db()
        self.assertEqual(self.o.status, "new")
        self.assertEqual(self.o.status_history.count(), 1)

    def test_ready_can_go_back_to_production_for_rework(self):
        for st in ("confirmed", "in_production", "ready"):
            self.go(st)
        self.assertEqual(self.go("in_production").status_code, 200)

    def test_terminal_orders_only_accept_payment_updates(self):
        for st in ("confirmed", "in_production", "ready", "delivered"):
            self.go(st)
        self.assertEqual(self.s.c_owner.patch(order_url(self.o), {"title": "x"}, format="json").status_code, 400)
        self.assertEqual(self.go("cancelled").status_code, 400)
        self.assertEqual(self.go("in_production").status_code, 400)
        self.assertEqual(self.s.c_owner.patch(order_url(self.o), {"paid_amount": "1000"}, format="json").data["payment_status"], "paid")
        self.go("cancelled")  # still rejected, and nothing leaked in
        self.assertEqual(Order.objects.get(pk=self.o.pk).status, "delivered")

    def test_cancelled_is_final_and_cancels_open_tasks(self):
        order = self.o
        open_t = make_task(self.s.owner, order, assigned_to=self.s.m_emp1.pk)
        review_t = make_task(self.s.owner, order, title="Edge band")
        Task.objects.filter(pk=review_t.pk).update(status="review")
        done_t = make_task(self.s.owner, order, title="Done already")
        Task.objects.filter(pk=done_t.pk).update(status="completed")
        self.assertEqual(self.go("cancelled", status_note="Customer left").status_code, 200)
        statuses = {t.title: t.status for t in Task.objects.filter(order=order)}
        self.assertEqual(statuses, {"Cut panels": "cancelled", "Edge band": "cancelled", "Done already": "completed"})
        self.assertEqual(open_t.status_history.last().note, "Order cancelled")
        self.assertEqual(self.go("new").status_code, 400)

    def test_cannot_add_tasks_to_a_closed_order(self):
        self.go("cancelled")
        r = self.s.c_owner.post(API + "tasks/", {"order": self.o.pk, "title": "late"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("order", r.data["error"]["fields"])

    def test_a_status_change_is_atomic(self):
        """If the task cancellation fails midway the order must not end up cancelled."""
        from unittest import mock
        make_task(self.s.owner, self.o)
        with mock.patch("apps.workshops.services._set_task_status", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                self.go("cancelled")
        self.o.refresh_from_db()
        self.assertEqual(self.o.status, "new")
        self.assertEqual(self.o.status_history.count(), 1)

    def test_workshop_cannot_be_changed(self):
        r = self.s.c_owner.patch(order_url(self.o), {"workshop": self.s.wsb.pk}, format="json")
        self.assertEqual(r.status_code, 400)
        self.o.refresh_from_db()
        self.assertEqual(self.o.workshop, self.s.ws)

    def test_deadline_updates(self):
        self.assertEqual(self.s.c_owner.patch(order_url(self.o), {"deadline": str(days(-2))}, format="json").status_code, 400)
        self.assertEqual(self.s.c_owner.patch(order_url(self.o), {"deadline": str(days(10)), "start_date": str(days(2))}, format="json").status_code, 200)
        self.assertEqual(self.s.c_owner.patch(order_url(self.o), {"start_date": str(days(20))}, format="json").status_code, 400)  # after the deadline


class OrderDeletionTests(TestCase):
    def setUp(self):
        self.s = Scene()

    def test_new_unpaid_orders_can_be_deleted(self):
        o = make_order(self.s.ws, self.s.owner)
        self.assertEqual(self.s.c_owner.delete(order_url(o)).status_code, 204)
        self.assertFalse(Order.objects.filter(pk=o.pk).exists())

    def test_financial_and_production_records_are_kept(self):
        paid = make_order(self.s.ws, self.s.owner, total_price="100", paid_amount="10")
        moving = make_order(self.s.ws, self.s.owner)
        self.s.c_owner.patch(order_url(moving), {"status": "confirmed"}, format="json")
        for o in (paid, moving):
            r = self.s.c_owner.delete(order_url(o))
            self.assertEqual(r.status_code, 409, r.data)
            self.assertTrue(Order.objects.filter(pk=o.pk).exists())

    def test_cancelled_unpaid_order_can_be_deleted_but_a_paid_one_cannot(self):
        o = make_order(self.s.ws, self.s.owner, total_price="100", paid_amount="10")
        self.s.c_owner.patch(order_url(o), {"status": "cancelled"}, format="json")
        self.assertEqual(self.s.c_owner.delete(order_url(o)).status_code, 409)
        o2 = make_order(self.s.ws, self.s.owner)
        self.s.c_owner.patch(order_url(o2), {"status": "cancelled"}, format="json")
        self.assertEqual(self.s.c_owner.delete(order_url(o2)).status_code, 204)

    def test_employee_and_strangers_cannot_delete(self):
        o = make_order(self.s.ws, self.s.owner, assigned_employee=self.s.m_emp1.pk)
        self.assertEqual(self.s.c_emp1.delete(order_url(o)).status_code, 403)
        self.assertEqual(self.s.c_emp2.delete(order_url(o)).status_code, 404)
        self.assertEqual(self.s.c_owner_b.delete(order_url(o)).status_code, 404)
        self.assertTrue(Order.objects.filter(pk=o.pk).exists())


class OrderAccessTests(TestCase):
    def setUp(self):
        self.s = Scene()
        self.assigned = make_order(self.s.ws, self.s.owner, title="Assigned", assigned_employee=self.s.m_emp1.pk, total_price="900", paid_amount="100")
        self.with_task = make_order(self.s.ws, self.s.owner, title="Has my task", total_price="500")
        make_task(self.s.owner, self.with_task, assigned_to=self.s.m_emp1.pk)
        self.hidden = make_order(self.s.ws, self.s.owner, title="Not for emp1")
        self.other_ws = make_order(self.s.wsb, self.s.owner_b, title="Other workshop")

    def titles(self, client, **params):
        return sorted(o["title"] for o in client.get(ORDERS, params).data["results"])

    def test_visibility_by_role(self):
        self.assertEqual(self.titles(self.s.c_owner), ["Assigned", "Has my task", "Not for emp1"])
        self.assertEqual(self.titles(self.s.c_emp1), ["Assigned", "Has my task"])
        self.assertEqual(self.titles(self.s.c_emp2), [])
        self.assertEqual(self.titles(self.s.c_stranger), [])
        self.assertEqual(self.titles(self.s.c_owner_b), ["Other workshop"])

    def test_detail_access_is_scoped_and_hidden_objects_are_404(self):
        self.assertEqual(self.s.c_emp1.get(order_url(self.assigned)).status_code, 200)
        self.assertEqual(self.s.c_emp1.get(order_url(self.with_task)).status_code, 200)
        for o in (self.hidden, self.other_ws):
            self.assertEqual(self.s.c_emp1.get(order_url(o)).status_code, 404)
        self.assertEqual(self.s.c_owner.get(order_url(self.other_ws)).status_code, 404)
        self.assertEqual(self.s.c_stranger.get(order_url(self.assigned)).status_code, 404)
        self.assertEqual(client_for().get(ORDERS).status_code, 401)

    def test_employees_never_see_money_or_the_customers_account(self):
        d = self.s.c_emp1.get(order_url(self.assigned)).data
        for f in ("total_price", "paid_amount", "payment_status", "outstanding_amount", "customer_user"):
            self.assertNotIn(f, d)
        self.assertEqual(d["customer_name"], "Ali Valiyev")
        self.assertIn("total_price", self.s.c_owner.get(order_url(self.assigned)).data)
        for row in self.s.c_emp1.get(ORDERS).data["results"]:
            self.assertNotIn("total_price", row)

    def test_employees_cannot_modify_orders(self):
        for body in ({"title": "x"}, {"status": "confirmed"}, {"paid_amount": "1"}, {"assigned_employee": self.s.m_emp2.pk}):
            self.assertEqual(self.s.c_emp1.patch(order_url(self.assigned), body, format="json").status_code, 403, body)
        self.assertEqual(self.s.c_emp1.patch(order_url(self.hidden), {"title": "x"}, format="json").status_code, 404)
        self.assertEqual(self.s.c_emp1.put(order_url(self.assigned), {"title": "x"}, format="json").status_code, 403)
        self.assigned.refresh_from_db()
        self.assertEqual((self.assigned.title, self.assigned.status), ("Assigned", "new"))

    def test_other_workshops_owner_cannot_modify(self):
        self.assertEqual(self.s.c_owner_b.patch(order_url(self.assigned), {"title": "x"}, format="json").status_code, 404)
        self.assertEqual(self.s.c_owner.patch(order_url(self.other_ws), {"title": "x"}, format="json").status_code, 404)

    def test_an_owner_of_one_workshop_is_only_an_employee_in_another(self):
        add_member(self.s.wsb, self.s.owner)  # owner of A is an employee of B
        mine_b = make_order(self.s.wsb, self.s.owner_b, title="B assigned")
        Order.objects.filter(pk=mine_b.pk).update(assigned_employee=self.s.wsb.members.get(user=self.s.owner))
        self.assertIn("B assigned", self.titles(self.s.c_owner))
        self.assertNotIn("Other workshop", self.titles(self.s.c_owner))               # only what is assigned to them in B
        self.assertEqual(self.s.c_owner.patch(order_url(mine_b), {"title": "x"}, format="json").status_code, 403)
        self.assertNotIn("total_price", self.s.c_owner.get(order_url(mine_b)).data)    # no money in B ...
        self.assertIn("total_price", self.s.c_owner.get(order_url(self.assigned)).data)  # ... but full access in A


class OrderListingTests(TestCase):
    def setUp(self):
        self.s = Scene()
        s = self.s
        self.a = make_order(s.ws, s.owner, title="Oak wardrobe", customer_name="Aziz", customer_phone="+998901111111", total_price="3000", paid_amount="3000",
                            deadline=str(days(5)), assigned_employee=s.m_emp1.pk)
        self.b = make_order(s.ws, s.owner, title="Kitchen", customer_name="Bobur", total_price="1000", paid_amount="200", deadline=str(days(20)))
        self.c = make_order(s.ws, s.owner, title="Desk", customer_name="Aziza", total_price="500")
        s.c_owner.patch(order_url(self.b), {"status": "confirmed"}, format="json")
        Order.objects.filter(pk=self.c.pk).update(deadline=days(-3), start_date=days(-10))   # an overdue order

    def q(self, **params):
        r = self.s.c_owner.get(ORDERS, params)
        self.assertEqual(r.status_code, 200, r.data)
        return [o["title"] for o in r.data["results"]]

    def test_filters(self):
        self.assertEqual(self.q(status="confirmed"), ["Kitchen"])
        self.assertEqual(self.q(payment_status="paid"), ["Oak wardrobe"])
        self.assertEqual(sorted(self.q(workshop=self.s.ws.pk)), ["Desk", "Kitchen", "Oak wardrobe"])
        self.assertEqual(self.q(assigned_employee=self.s.m_emp1.pk), ["Oak wardrobe"])
        self.assertEqual(self.q(deadline_after=str(days(10))), ["Kitchen"])
        self.assertEqual(sorted(self.q(deadline_before=str(days(10)))), ["Desk", "Oak wardrobe"])
        self.assertEqual(self.q(overdue="true"), ["Desk"])
        self.assertEqual(sorted(self.q(overdue="false")), ["Kitchen", "Oak wardrobe"])
        self.assertEqual(self.q(created_after=str(days(1))), [])
        self.assertEqual(len(self.q(created_before=str(days(1)))), 3)

    def test_invalid_filter_values_are_errors_not_silently_ignored(self):
        self.assertEqual(self.s.c_owner.get(ORDERS, {"status": "bogus"}).status_code, 400)
        self.assertEqual(self.s.c_owner.get(ORDERS, {"deadline_after": "yesterday"}).status_code, 400)

    def test_overdue_ignores_finished_orders(self):
        Order.objects.filter(pk=self.c.pk).update(status="delivered")
        self.assertEqual(self.q(overdue="true"), [])

    def test_search(self):
        self.assertEqual(self.q(search="wardrobe"), ["Oak wardrobe"])
        self.assertEqual(sorted(self.q(search="Aziz")), ["Desk", "Oak wardrobe"])
        self.assertEqual(self.q(search="901111111"), ["Oak wardrobe"])
        self.assertEqual(self.q(search=self.b.order_number), ["Kitchen"])
        self.assertEqual(self.q(search="no such thing"), [])

    def test_sorting(self):
        self.assertEqual(self.q(ordering="total_price", workshop=self.s.ws.pk), ["Desk", "Kitchen", "Oak wardrobe"])
        self.assertEqual(self.q(ordering="-total_price", workshop=self.s.ws.pk), ["Oak wardrobe", "Kitchen", "Desk"])
        self.assertEqual(self.q(ordering="order_number"), ["Oak wardrobe", "Kitchen", "Desk"])
        self.assertEqual(self.q(ordering="-order_number"), ["Desk", "Kitchen", "Oak wardrobe"])
        self.assertEqual(self.q(ordering="deadline")[0], "Desk")
        self.assertEqual(self.q(), ["Desk", "Kitchen", "Oak wardrobe"])   # default: newest first

    def test_pagination(self):
        r = self.s.c_owner.get(ORDERS, {"page_size": 2}).data
        self.assertEqual((r["count"], len(r["results"]), bool(r["next"]), r["previous"]), (3, 2, True, None))
        r2 = self.s.c_owner.get(ORDERS, {"page_size": 2, "page": 2}).data
        self.assertEqual(len(r2["results"]), 1)
        self.assertEqual(self.s.c_owner.get(ORDERS, {"page": 9}).status_code, 404)
        self.assertEqual(len(self.s.c_owner.get(ORDERS, {"page_size": 1000}).data["results"]), 3)  # capped at 100, not an error

    def test_employee_mine_filter_and_money_probing_is_blocked(self):
        self.assertEqual(self.s.c_emp1.get(ORDERS, {"mine": "true"}).data["count"], 1)
        self.assertEqual(self.s.c_emp1.get(ORDERS, {"mine": "false"}).data["count"], 0)
        # filtering or sorting on money would leak relative values to employees
        for params in ({"ordering": "total_price"}, {"ordering": "-total_price"}, {"payment_status": "paid"}):
            self.assertEqual(self.s.c_emp1.get(ORDERS, params).status_code, 400, params)
        self.assertEqual(self.s.c_emp1.get(ORDERS, {"ordering": "total_price", "workshop": self.s.ws.pk}).status_code, 400)
        self.assertEqual(self.s.c_owner.get(ORDERS, {"ordering": "total_price", "workshop": self.s.ws.pk}).status_code, 200)
        # a pure owner may sort everything they see; someone who is also an employee elsewhere must name the owned workshop
        self.assertEqual(self.s.c_owner.get(ORDERS, {"ordering": "total_price"}).status_code, 200)
        add_member(self.s.wsb, self.s.owner)
        self.assertEqual(self.s.c_owner.get(ORDERS, {"ordering": "total_price"}).status_code, 400)
        self.assertEqual(self.s.c_owner.get(ORDERS, {"ordering": "total_price", "workshop": self.s.ws.pk}).status_code, 200)
