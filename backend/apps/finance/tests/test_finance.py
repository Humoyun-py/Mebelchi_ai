from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.core.tests.helpers import client_for, make_user
from apps.finance import services
from apps.finance.models import OrderPayment, PlatformSettings
from apps.marketplace.tests.helpers import FURN, customer, shop
from apps.notifications.models import Notification
from apps.workshops.models import Order

M = "/api/v1/marketplace/"
FIN = "/api/v1/admin-api/finance/"


class SplitTests(SimpleTestCase):
    def test_the_spec_example(self):
        self.assertEqual(services.split(Decimal("1000"), Decimal("20")), (Decimal("200.00"), Decimal("800.00")))

    def test_parts_always_add_up_to_the_total_to_the_cent(self):
        for total in ("0.01", "0.03", "333.33", "99.99", "1234567.89", "10"):
            for pct in ("20", "12.5", "0", "100", "33.33"):
                c, w = services.split(Decimal(total), Decimal(pct))
                self.assertEqual(c + w, Decimal(total).quantize(Decimal("0.01")), (total, pct))
                self.assertGreaterEqual(w, 0)

    def test_rounding_is_half_up(self):
        self.assertEqual(services.split(Decimal("333.33"), Decimal("20"))[0], Decimal("66.67"))
        self.assertEqual(services.money("0.005"), Decimal("0.01"))


class Base(TestCase):
    def setUp(self):
        self.ws = shop("Alpha", "a@x.com")
        self.user, self.c = customer()
        self.admin = make_user("adm@x.com", "maker", is_staff=True)
        self.ca, self.cw = client_for(self.admin), client_for(self.ws.owner)
        r = self.c.post(M + "orders/", {"workshop": self.ws.pk, "furniture": FURN}, format="json")
        self.oid, self.total = r.data["id"], Decimal(r.data["total_price"])
        self.cw.patch(f"/api/v1/orders/{self.oid}/", {"status": "confirmed"}, format="json")

    def pay(self, amount, **kw):
        return self.c.post(f"{M}orders/{self.oid}/payments/", {"amount": str(amount), "method": "bank_transfer", **kw}, format="json")

    def order(self):
        return Order.objects.get(pk=self.oid)


class SettingsTests(Base):
    def test_default_is_20_and_admin_changes_it_with_validation_and_audit(self):
        self.assertEqual(PlatformSettings.get().commission_percent, Decimal("20.00"))
        self.assertEqual(self.ca.get(FIN + "commission/").data["commission_percent"], Decimal("20.00"))
        self.assertEqual(self.ca.patch(FIN + "commission/", {"commission_percent": "12.5"}, format="json").status_code, 200)
        self.assertTrue(AuditLog.objects.filter(event="finance.commission_changed").exists())
        for bad in ("-1", "101", "abc", "12.345", None):
            self.assertEqual(self.ca.patch(FIN + "commission/", {"commission_percent": bad}, format="json").status_code, 400, bad)
        self.assertEqual(PlatformSettings.get().commission_percent, Decimal("12.50"))

    def test_only_admins(self):
        for c in (self.c, self.cw, APIClient()):
            self.assertIn(c.patch(FIN + "commission/", {"commission_percent": "1"}, format="json").status_code, (401, 403))
            self.assertIn(c.get(FIN + "summary/").status_code, (401, 403))
            self.assertIn(c.get(FIN + "payments/").status_code, (401, 403))


class PaymentTests(Base):
    def test_customer_report_counts_only_after_admin_confirmation(self):
        r = self.pay("10.00", reference="TRX-1")
        self.assertEqual((r.status_code, r.data["status"]), (201, "pending"))
        self.assertEqual(self.order().paid_amount, 0)
        c = self.ca.post(f"{FIN}payments/{r.data['id']}/confirm/")
        self.assertEqual((c.status_code, c.data["status"]), (200, "confirmed"))
        o = self.order()
        self.assertEqual((o.paid_amount, o.payment_status), (Decimal("10.00"), "partially_paid"))
        self.assertTrue(AuditLog.objects.filter(event="payment.payment_confirmed").exists())
        self.assertTrue(Notification.objects.filter(user=self.user, body__contains="confirmed").exists())

    def test_cannot_confirm_twice_so_nothing_is_counted_twice(self):
        pid = self.pay("10").data["id"]
        self.ca.post(f"{FIN}payments/{pid}/confirm/")
        self.assertEqual(self.ca.post(f"{FIN}payments/{pid}/confirm/").status_code, 400)
        self.assertEqual(self.ca.post(f"{FIN}payments/{pid}/reject/", {"reason": "x"}, format="json").status_code, 400)
        self.assertEqual(self.order().paid_amount, Decimal("10.00"))

    def test_idempotency_key_makes_a_retry_return_the_same_payment(self):
        a, b = self.pay("10", idempotency_key="k1"), self.pay("10", idempotency_key="k1")
        self.assertEqual((a.status_code, b.status_code, a.data["id"] == b.data["id"]), (201, 200, True))
        self.assertEqual(OrderPayment.objects.count(), 1)

    def test_same_receipt_cannot_be_recorded_twice(self):
        self.assertEqual(self.pay("10", reference="R1").status_code, 201)
        self.assertEqual(self.pay("10", reference="R1").status_code, 400)

    def test_rejected_receipt_can_be_resubmitted(self):
        pid = self.pay("10", reference="R1").data["id"]
        self.assertEqual(self.ca.post(f"{FIN}payments/{pid}/reject/", {}, format="json").status_code, 400)                  # reason required
        self.assertEqual(self.ca.post(f"{FIN}payments/{pid}/reject/", {"reason": "Not found"}, format="json").status_code, 200)
        self.assertEqual(self.pay("10", reference="R1").status_code, 201)
        self.assertEqual(self.order().paid_amount, 0)

    def test_full_payment_marks_paid_and_overpaying_is_refused(self):
        self.assertEqual(self.pay(self.total + 1).status_code, 400)
        pid = self.pay(self.total).data["id"]
        self.ca.post(f"{FIN}payments/{pid}/confirm/")
        self.assertEqual(self.order().payment_status, "paid")
        self.assertEqual(self.pay("1").status_code, 400)

    def test_two_pending_payments_cannot_together_overpay(self):
        half = (self.total / 2).quantize(Decimal("0.01"))
        a, b = self.pay(half).data["id"], self.pay(self.total - half).data["id"]
        self.assertEqual(self.ca.post(f"{FIN}payments/{a}/confirm/").status_code, 200)
        self.assertEqual(self.ca.post(f"{FIN}payments/{b}/confirm/").status_code, 200)
        self.assertEqual((self.order().paid_amount, self.order().payment_status), (self.total, "paid"))
        c = self.ca.post(FIN + "payments/", {"order": self.oid, "amount": "1", "confirm": True}, format="json")
        self.assertEqual(c.status_code, 400)

    def test_bad_amounts_and_methods(self):
        for amt in ("0", "-5", "abc"):
            self.assertEqual(self.pay(amt).status_code, 400, amt)
        self.assertEqual(self.c.post(f"{M}orders/{self.oid}/payments/", {"amount": "1", "method": "crypto"}, format="json").status_code, 400)

    def test_pending_or_rejected_orders_cannot_be_paid(self):
        r = self.c.post(M + "orders/", {"workshop": self.ws.pk, "furniture": FURN}, format="json")
        self.assertEqual(self.c.post(f"{M}orders/{r.data['id']}/payments/", {"amount": "5"}, format="json").status_code, 400)

    def test_admin_records_and_confirms_in_one_step(self):
        r = self.ca.post(FIN + "payments/", {"order": self.oid, "amount": "25.50", "method": "cash", "confirm": True}, format="json")
        self.assertEqual((r.status_code, r.data["status"]), (201, "confirmed"))
        self.assertEqual(self.order().paid_amount, Decimal("25.50"))

    def test_refunds_partial_and_full(self):
        self.ca.post(FIN + "payments/", {"order": self.oid, "amount": "100", "confirm": True}, format="json")
        r = self.ca.post(FIN + "payments/", {"order": self.oid, "kind": "refund", "amount": "30", "confirm": True}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((self.order().paid_amount, self.order().payment_status), (Decimal("70.00"), "partially_paid"))
        self.assertEqual(self.ca.post(FIN + "payments/", {"order": self.oid, "kind": "refund", "amount": "71", "confirm": True}, format="json").status_code, 400)
        self.ca.post(FIN + "payments/", {"order": self.oid, "kind": "refund", "amount": "70", "confirm": True}, format="json")
        self.assertEqual(self.order().payment_status, "refunded")
        self.assertEqual(self.pay("5").status_code, 400)                                                                    # record is closed

    def test_admin_listing_and_filters(self):
        self.pay("10")
        r = self.ca.get(FIN + "payments/", {"status": "pending"})
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(self.ca.get(FIN + "payments/", {"status": "confirmed"}).data["count"], 0)


class SummaryTests(Base):
    def test_report_adds_up(self):
        self.ca.post(FIN + "payments/", {"order": self.oid, "amount": str((self.total / 2).quantize(Decimal("0.01"))), "confirm": True}, format="json")
        d = self.ca.get(FIN + "summary/").data
        o = self.order()
        self.assertEqual((d["booked"]["orders"], d["booked"]["total"], d["booked"]["commission"], d["booked"]["workshop_amount"]),
                         (1, o.total_price, o.commission_amount, o.workshop_amount))
        self.assertEqual(d["booked"]["commission"] + d["booked"]["workshop_amount"], d["booked"]["total"])
        self.assertEqual((d["collected"]["payments"], d["collected"]["refunds"]), (1, 0))
        w = d["by_workshop"][0]
        self.assertEqual((w["workshop"], w["orders"]), (self.ws.pk, 1))
        self.assertAlmostEqual(float(w["commission_covered"] + w["payable_covered"]), float(w["paid_so_far"]), delta=0.02)
        self.assertEqual(self.ca.get(FIN + "summary/", {"workshop": self.ws.pk + 99}).data["booked"]["orders"], 0)
        self.assertEqual(self.ca.get(FIN + "summary/", {"from": "bad"}).status_code, 400)

    def test_pending_and_cancelled_orders_are_not_booked(self):
        self.c.post(M + "orders/", {"workshop": self.ws.pk, "furniture": FURN}, format="json")
        self.assertEqual(self.ca.get(FIN + "summary/").data["booked"]["orders"], 1)
