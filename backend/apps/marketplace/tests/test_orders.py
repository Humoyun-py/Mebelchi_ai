import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.tests.helpers import client_for, make_user
from apps.marketplace import tasks
from apps.marketplace.tests.helpers import FURN, customer, shop
from apps.notifications.models import Notification
from apps.workshops.models import Order, Workshop

M = "/api/v1/marketplace/"
ORD = "/api/v1/orders/"
FIN = "/api/v1/admin-api/finance/"


class Base(TestCase):
    def setUp(self):
        self.w1 = shop("Alpha", "a@x.com", scale=0.8)
        self.w2 = shop("Beta", "b@x.com", scale=1.2)
        self.user, self.c = customer()
        self.other, self.co = customer("other@x.com")
        self.admin = make_user("adm@x.com", "maker", is_staff=True)
        self.ca, self.cw1, self.cw2 = client_for(self.admin), client_for(self.w1.owner), client_for(self.w2.owner)

    def place(self, ws=None, c=None, **kw):
        body = {"workshop": (ws or self.w1).pk, "furniture": FURN, **kw}
        return (c or self.c).post(M + "orders/", body, format="json")

    def placed(self, **kw):
        r = self.place(**kw)
        self.assertEqual(r.status_code, 201, r.data)
        return r.data

    def set_status(self, c, oid, status, note=""):
        return c.patch(f"{ORD}{oid}/", {"status": status, "status_note": note}, format="json")

    def walk(self, oid, c=None, to=("confirmed", "in_production", "quality_check", "ready", "delivery", "delivered")):
        for s in to:
            r = self.set_status(c or self.cw1, oid, s)
            self.assertEqual(r.status_code, 200, (s, r.data))


class PlaceOrderTests(Base):
    def test_order_starts_pending_with_a_server_side_price_and_a_commission_split(self):
        o = self.placed(total_price="1")                                  # a client-sent price is ignored
        self.assertEqual(o["status"], "pending")
        self.assertGreater(Decimal(o["total_price"]), 50)
        row = Order.objects.get(pk=o["id"])
        self.assertEqual((row.source, row.commission_percent, row.customer_user_id), ("marketplace", Decimal("20.00"), self.user.id))
        self.assertEqual(row.commission_amount + row.workshop_amount, row.total_price)
        self.assertEqual(row.commission_amount, (row.total_price * Decimal("0.2")).quantize(Decimal("0.01")))
        self.assertEqual((row.quote["category"], row.quote["quantity"]), ("kitchen", 1))
        self.assertTrue(row.quote["lines"])

    def test_workshop_is_told_and_customer_gets_the_24_hour_promise(self):
        o = self.placed()
        self.assertTrue(Notification.objects.filter(user=self.w1.owner, title__contains=o["order_number"]).exists())
        n = Notification.objects.get(user=self.user, title__contains=o["order_number"])
        self.assertIn("24 hours", n.body)

    def test_workshop_sees_commission_and_payable_the_customer_does_not(self):
        o = self.placed()
        w = self.cw1.get(f"{ORD}{o['id']}/").data
        self.assertEqual((w["status"], w["source"], w["commission_percent"]), ("pending", "marketplace", "20.00"))
        self.assertEqual(Decimal(w["commission_amount"]) + Decimal(w["workshop_amount"]), Decimal(w["total_price"]))
        self.assertNotIn("commission_amount", o)
        self.assertNotIn("workshop_amount", o)
        self.assertNotIn("assigned_employee", o)

    def test_ineligible_workshops_and_bad_input_are_refused(self):
        Workshop.objects.filter(pk=self.w1.pk).update(is_accepting_orders=False)
        self.assertEqual(self.place().status_code, 400)
        self.assertEqual(self.place(ws=self.w2, quantity=0).status_code, 400)
        self.assertEqual(self.c.post(M + "orders/", {"furniture": FURN}, format="json").status_code, 400)
        self.assertEqual(self.c.post(M + "orders/", {"workshop": 99999, "furniture": FURN}, format="json").status_code, 400)
        self.assertEqual(APIClient().post(M + "orders/", {}, format="json").status_code, 401)
        self.assertEqual(Order.objects.count(), 0)

    def test_customers_see_only_their_own_orders(self):
        o = self.placed()
        self.assertEqual([x["id"] for x in self.c.get(M + "orders/").data["results"]], [o["id"]])
        self.assertEqual(self.co.get(M + "orders/").data["results"], [])
        for call in (self.co.get(f"{M}orders/{o['id']}/"), self.co.post(f"{M}orders/{o['id']}/cancel/"), self.co.post(f"{M}orders/{o['id']}/review/", {"stars": 5}, format="json"),
                     self.co.post(f"{M}orders/{o['id']}/payments/", {"amount": "1"}, format="json")):
            self.assertEqual(call.status_code, 404)

    def test_another_workshop_cannot_see_the_order(self):
        o = self.placed()
        self.assertEqual(self.cw2.get(f"{ORD}{o['id']}/").status_code, 404)

    def test_workshop_cannot_change_the_price_or_the_payment_of_a_marketplace_order(self):
        o = self.placed()
        for body in ({"total_price": "1.00"}, {"paid_amount": "1.00"}):
            self.assertEqual(self.cw1.patch(f"{ORD}{o['id']}/", body, format="json").status_code, 400, body)

    def test_new_commission_rate_affects_only_new_orders(self):
        first = self.placed()
        self.assertEqual(self.ca.patch(FIN + "commission/", {"commission_percent": "15"}, format="json").status_code, 200)
        second = self.placed()
        self.assertEqual(Order.objects.get(pk=first["id"]).commission_percent, Decimal("20.00"))
        self.assertEqual(Order.objects.get(pk=second["id"]).commission_percent, Decimal("15.00"))

    def test_catalog_item_order(self):
        from apps.furniture.models import FurnitureTemplate
        item = FurnitureTemplate.objects.create(slug="k1", category="kitchen", name="Kitchen unit", workshop=self.w1, price=Decimal("1000"), status="approved",
                                                defaults={k: v for k, v in FURN.items() if k != "category"})
        r = self.c.post(M + "orders/", {"workshop": self.w1.pk, "catalog_item": item.pk, "quantity": 2}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        row = Order.objects.get(pk=r.data["id"])
        self.assertEqual((row.total_price, row.commission_amount, row.workshop_amount, row.catalog_item_id), (Decimal("2000.00"), Decimal("400.00"), Decimal("1600.00"), item.pk))


class LifecycleTests(Base):
    def test_full_happy_path_with_customer_notifications(self):
        o = self.placed()
        self.walk(o["id"])
        d = self.c.get(f"{M}orders/{o['id']}/").data
        self.assertEqual(d["status"], "delivered")
        self.assertEqual(d["workshop"]["phone"], self.w1.phone or None)
        statuses = [h["to"] for h in d["history"]]
        self.assertEqual(statuses, ["pending", "confirmed", "in_production", "quality_check", "ready", "delivery", "delivered"])
        self.assertGreaterEqual(Notification.objects.filter(user=self.user).count(), 6)

    def test_invalid_jumps_and_allowed_next_statuses(self):
        o = self.placed()
        self.assertEqual(self.set_status(self.cw1, o["id"], "in_production").status_code, 400)
        self.assertEqual(self.set_status(self.cw1, o["id"], "delivered").status_code, 400)
        self.assertEqual(self.cw1.get(f"{ORD}{o['id']}/").data["allowed_next_statuses"], ["cancelled", "confirmed", "rejected"])

    def test_rejection_needs_a_reason_and_tells_the_customer(self):
        o = self.placed()
        self.assertEqual(self.set_status(self.cw1, o["id"], "rejected").status_code, 400)
        self.assertEqual(self.set_status(self.cw1, o["id"], "rejected", "No capacity this month").status_code, 200)
        d = self.c.get(f"{M}orders/{o['id']}/").data
        self.assertEqual((d["status"], d["rejection_reason"], d["actions"]["reassign"]), ("rejected", "No capacity this month", True))
        self.assertTrue(Notification.objects.filter(user=self.user, body__contains="No capacity").exists())
        self.assertEqual(self.set_status(self.cw1, o["id"], "confirmed").status_code, 400)           # rejected is final

    def test_rejected_order_is_rerouted_to_another_workshop_only_once(self):
        o = self.placed()
        self.set_status(self.cw1, o["id"], "rejected", "Busy")
        alt = self.c.get(f"{M}orders/{o['id']}/alternatives/").data
        self.assertEqual([x["workshop"] for x in alt["options"]], [self.w2.pk])                      # the refusing workshop is never offered
        self.assertEqual(self.c.post(f"{M}orders/{o['id']}/reassign/", {"workshop": self.w1.pk}, format="json").status_code, 400)
        r = self.c.post(f"{M}orders/{o['id']}/reassign/", {"workshop": self.w2.pk}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["status"], r.data["rerouted_from"], r.data["workshop"]["id"]), ("pending", o["id"], self.w2.pk))
        self.assertEqual(self.c.post(f"{M}orders/{o['id']}/reassign/", {"workshop": self.w2.pk}, format="json").status_code, 400)
        self.assertEqual(self.c.get(f"{M}orders/{o['id']}/").data["actions"]["reassign"], False)

    def test_reassign_and_alternatives_only_for_rejected_orders(self):
        o = self.placed()
        self.assertEqual(self.c.get(f"{M}orders/{o['id']}/alternatives/").status_code, 400)
        self.assertEqual(self.c.post(f"{M}orders/{o['id']}/reassign/", {"workshop": self.w2.pk}, format="json").status_code, 400)

    def test_customer_can_cancel_before_production_and_it_stops_the_reminders(self):
        o = self.placed()
        r = self.c.post(f"{M}orders/{o['id']}/cancel/")
        self.assertEqual((r.status_code, r.data["status"]), (200, "cancelled"))
        Order.objects.filter(pk=o["id"]).update(created_at=timezone.now() - datetime.timedelta(hours=9))
        self.assertEqual(tasks.send_reminders(), 0)
        self.assertEqual(self.c.post(f"{M}orders/{o['id']}/cancel/").status_code, 400)

    def test_customer_cannot_cancel_once_production_started(self):
        o = self.placed()
        self.walk(o["id"], to=("confirmed", "in_production"))
        self.assertEqual(self.c.post(f"{M}orders/{o['id']}/cancel/").status_code, 400)

    def test_review_updates_the_workshop_rating_once(self):
        o = self.placed()
        self.assertEqual(self.c.post(f"{M}orders/{o['id']}/review/", {"stars": 5}, format="json").status_code, 400)        # not completed yet
        self.walk(o["id"])
        self.assertEqual(self.c.post(f"{M}orders/{o['id']}/review/", {"stars": 9}, format="json").status_code, 400)
        self.assertEqual(self.c.post(f"{M}orders/{o['id']}/review/", {"stars": 4, "comment": "Good"}, format="json").status_code, 201)
        self.assertEqual(self.c.post(f"{M}orders/{o['id']}/review/", {"stars": 5}, format="json").status_code, 400)
        self.w1.refresh_from_db()
        self.assertEqual((self.w1.rating_count, self.w1.rating_avg), (1, Decimal("4.00")))
        o2 = self.placed()
        self.walk(o2["id"])
        self.c.post(f"{M}orders/{o2['id']}/review/", {"stars": 5}, format="json")
        self.w1.refresh_from_db()
        self.assertEqual((self.w1.rating_count, self.w1.rating_avg), (2, Decimal("4.50")))

    def test_employees_do_not_see_commission(self):
        o = self.placed()
        emp = make_user("emp@x.com", "workshop")
        from apps.workshops.models import WorkshopMember
        m = WorkshopMember.objects.create(workshop=self.w1, user=emp, role="employee", status="active")
        Order.objects.filter(pk=o["id"]).update(assigned_employee=m)
        d = client_for(emp).get(f"{ORD}{o['id']}/").data
        for k in ("commission_amount", "workshop_amount", "commission_percent", "total_price", "quote"):
            self.assertNotIn(k, d)


class ReminderTests(Base):
    def old(self, oid, hours):
        Order.objects.filter(pk=oid).update(created_at=timezone.now() - datetime.timedelta(hours=hours))

    def test_no_reminder_before_4_hours(self):
        o = self.placed()
        self.old(o["id"], 3)
        self.assertEqual(tasks.send_reminders(), 0)

    def test_one_reminder_per_4_hours_and_never_twice_in_the_same_window(self):
        o = self.placed()
        self.old(o["id"], 5)
        self.assertEqual(tasks.send_reminders(), 1)
        self.assertEqual(tasks.send_reminders(), 0)                                                  # same window: nothing more
        self.assertEqual(Order.objects.get(pk=o["id"]).reminders_sent, 1)
        later = timezone.now() + datetime.timedelta(hours=4, minutes=1)
        self.assertEqual(tasks.send_reminders(later), 1)
        self.assertEqual(Notification.objects.filter(user=self.w1.owner, title__startswith="Reminder").count(), 2)

    def test_reminders_are_limited_then_customer_and_admin_are_told_once(self):
        o = self.placed()
        self.old(o["id"], 1)
        now = timezone.now()
        total = 0
        for i in range(1, 12):
            total += tasks.send_reminders(now + datetime.timedelta(hours=4 * i + 1))
        self.assertEqual(total, 6)
        self.assertEqual(Order.objects.get(pk=o["id"]).reminders_sent, 6)
        self.assertEqual(Notification.objects.filter(user=self.user, body__contains="has not answered").count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.admin, title__startswith="Unanswered").count(), 1)

    def test_reminders_stop_when_the_workshop_answers(self):
        for status, note in (("confirmed", ""), ("rejected", "no")):
            o = self.placed()
            self.old(o["id"], 5)
            self.set_status(self.cw1, o["id"], status, note)
        self.assertEqual(tasks.send_reminders(), 0)

    def test_manual_and_non_pending_orders_are_never_reminded(self):
        Order.objects.create(workshop=self.w1, order_number="M-1", customer_name="x", title="t", status="pending")        # manual source
        Order.objects.filter(order_number="M-1").update(created_at=timezone.now() - datetime.timedelta(hours=30))
        self.assertEqual(tasks.send_reminders(), 0)

    def test_celery_task_wrapper(self):
        o = self.placed()
        self.old(o["id"], 5)
        self.assertEqual(tasks.remind_pending_orders(), 1)
