import base64
import json
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import Client, SimpleTestCase, TestCase, override_settings

from apps.audit.models import AuditLog
from apps.finance.models import OrderPayment, PaymentTransaction as Tx
from apps.finance.providers import payme
from apps.marketplace.tests.helpers import FURN, customer, shop
from apps.notifications.models import Notification
from apps.workshops.models import Order

URL = "/api/v1/payments/webhook/payme/"
CFG = dict(PAYME_LOGIN="Paycom", PAYME_KEY="test-key-0123456789", PAYME_MERCHANT_ID="587f72c72cac0d162c722ae2", PAYME_ACCOUNT_FIELD="order_id")
AUTH = "Basic " + base64.b64encode(b"Paycom:test-key-0123456789").decode()
TID = "5305e3bab097f420a62ced0b"
TID2 = "5305e3bab097f420a62ced0c"
SUM = 1_000_000                       # sum
TIYIN = SUM * 100


def rpc(method, params, rid=1, auth=AUTH, raw=None, http_method="post"):
    c = Client()
    kw = {"HTTP_AUTHORIZATION": auth} if auth else {}
    body = raw if raw is not None else json.dumps({"method": method, "params": params, "id": rid})
    r = getattr(c, http_method)(URL, data=body, content_type="text/json; charset=UTF-8", **kw) if http_method == "post" else getattr(c, http_method)(URL, **kw)
    return r.status_code, r.json()


@override_settings(**CFG)
class Base(TestCase):
    def setUp(self):
        self.ws = shop("Alpha", "a@x.com")
        self.user, self.c = customer()
        from apps.core.tests.helpers import client_for
        self.cw = client_for(self.ws.owner)
        r = self.c.post("/api/v1/marketplace/orders/", {"workshop": self.ws.pk, "furniture": FURN}, format="json")
        self.oid = r.data["id"]
        self.cw.patch(f"/api/v1/orders/{self.oid}/", {"status": "confirmed"}, format="json")
        o = Order.objects.get(pk=self.oid)
        Order.objects.filter(pk=o.pk).update(total_price=Decimal(SUM), quote={**o.quote, "currency": "UZS"})
        self.num = o.order_number

    def acct(self):
        return {"order_id": self.num}

    def create(self, tid=TID, amount=TIYIN, t=1_700_000_000_000):
        return rpc("CreateTransaction", {"id": tid, "time": t, "amount": amount, "account": self.acct()})

    def perform(self, tid=TID):
        return rpc("PerformTransaction", {"id": tid})

    def order(self):
        return Order.objects.get(pk=self.oid)


class CheckoutUrlTests(SimpleTestCase):
    @override_settings(**CFG, PAYME_CHECKOUT_URL="https://checkout.paycom.uz")
    def test_matches_the_documentation_example(self):
        o = Order(order_number="197", total_price=Decimal("5.00"), paid_amount=Decimal("0"))
        self.assertEqual(payme.checkout_url(o), "https://checkout.paycom.uz/bT01ODdmNzJjNzJjYWMwZDE2MmM3MjJhZTI7YWMub3JkZXJfaWQ9MTk3O2E9NTAw")


class DisabledTests(TestCase):
    def test_everything_is_off_without_configuration(self):
        self.assertEqual(rpc("CheckTransaction", {"id": "x"})[0], 503)

    def test_click_and_uzum_are_not_implemented_and_unknown_is_404(self):
        for p, code in (("click", 503), ("uzum", 503), ("nope", 404)):
            self.assertEqual(Client().post(f"/api/v1/payments/webhook/{p}/", data="{}", content_type="application/json").status_code, code, p)
        self.assertEqual(Tx.objects.count(), 0)

    @override_settings(PAYME_LOGIN="Paycom", PAYME_KEY="")
    def test_login_without_key_is_off(self):
        self.assertEqual(rpc("CheckTransaction", {"id": "x"})[0], 503)


class ProtocolTests(Base):
    def test_authorisation(self):
        for bad in (None, "Basic", "Bearer abc", "Basic !!!", "Basic " + base64.b64encode(b"Paycom:wrong").decode(), "Basic " + base64.b64encode(b"Other:test-key-0123456789").decode()):
            st, body = rpc("CheckTransaction", {"id": TID}, auth=bad)
            self.assertEqual((st, body["error"]["code"]), (200, -32504), bad)
        self.assertEqual(Tx.objects.count(), 0)

    def test_nothing_changes_without_valid_authorisation(self):
        rpc("CreateTransaction", {"id": TID, "time": 1, "amount": TIYIN, "account": self.acct()}, auth=None)
        self.assertEqual(Tx.objects.count(), 0)

    def test_non_post(self):
        self.assertEqual(rpc("", {}, http_method="get")[1]["error"]["code"], -32300)

    def test_malformed_requests(self):
        self.assertEqual(rpc("", {}, raw="{not json")[1]["error"]["code"], -32700)
        for raw in ('[]', '{"method": 1, "params": {}}', '{"method": "GetStatement"}', '{"method":"GetStatement","params":[]}'):
            self.assertEqual(rpc("", {}, raw=raw)[1]["error"]["code"], -32600, raw)
        st, body = rpc("Nope", {})
        self.assertEqual((body["error"]["code"], body["error"]["data"]), (-32601, "Nope"))

    def test_error_shape_has_localised_message_and_echoes_id(self):
        st, body = rpc("CheckPerformTransaction", {"amount": 1, "account": {"order_id": "nope"}}, rid=77)
        self.assertEqual((body["id"], body["error"]["code"], body["error"]["data"]), (77, -31050, "order_id"))
        self.assertEqual(set(body["error"]["message"]), {"ru", "uz", "en"})
        self.assertNotIn("result", body)


class CheckPerformTests(Base):
    def test_ok(self):
        st, body = rpc("CheckPerformTransaction", {"amount": TIYIN, "account": self.acct()})
        self.assertEqual(body["result"], {"allow": True})

    def test_wrong_amounts(self):
        for amt in (TIYIN - 1, TIYIN + 1, 0, -5, "100", None, True, 1.5):
            self.assertEqual(rpc("CheckPerformTransaction", {"amount": amt, "account": self.acct()})[1]["error"]["code"], -31001, amt)

    def test_account_problems(self):
        for acct in ({}, {"order_id": ""}, {"order_id": "ZZZ"}, {"wrong": self.num}, None, {"order_id": 5}):
            self.assertEqual(rpc("CheckPerformTransaction", {"amount": TIYIN, "account": acct})[1]["error"]["code"], -31050, acct)

    def test_only_uzs_orders(self):
        o = self.order()
        Order.objects.filter(pk=o.pk).update(quote={**o.quote, "currency": "USD"})
        self.assertEqual(rpc("CheckPerformTransaction", {"amount": TIYIN, "account": self.acct()})[1]["error"]["code"], -31051)

    def test_unpayable_states(self):
        Order.objects.filter(pk=self.oid).update(status="pending")
        self.assertEqual(rpc("CheckPerformTransaction", {"amount": TIYIN, "account": self.acct()})[1]["error"]["code"], -31051)
        Order.objects.filter(pk=self.oid).update(status="confirmed", payment_status="paid")
        self.assertEqual(rpc("CheckPerformTransaction", {"amount": TIYIN, "account": self.acct()})[1]["error"]["code"], -31051)

    def test_non_marketplace_order_is_invisible(self):
        Order.objects.filter(pk=self.oid).update(source="manual")
        self.assertEqual(rpc("CheckPerformTransaction", {"amount": TIYIN, "account": self.acct()})[1]["error"]["code"], -31050)


class CreateTests(Base):
    def test_create_and_state(self):
        st, body = self.create()
        r = body["result"]
        self.assertEqual((r["state"], r["transaction"]), (1, str(Tx.objects.get().pk)))
        t = Tx.objects.get()
        self.assertEqual((t.amount_minor, t.status, t.order_id, t.provider_time_ms), (TIYIN, "created", self.oid, 1_700_000_000_000))

    def test_repeat_is_idempotent(self):
        a = self.create()[1]["result"]
        b = self.create()[1]["result"]
        self.assertEqual(a, b)
        self.assertEqual(Tx.objects.count(), 1)

    def test_amount_is_checked(self):
        self.assertEqual(self.create(amount=TIYIN - 100)[1]["error"]["code"], -31001)
        self.assertEqual(Tx.objects.count(), 0)

    def test_second_open_invoice_for_the_order_is_refused(self):
        self.create()
        st, body = self.create(tid=TID2)
        self.assertEqual(body["error"]["code"], -31099)
        self.assertEqual(Tx.objects.count(), 1)

    def test_bad_params(self):
        for p in ({"id": "", "time": 1, "amount": TIYIN, "account": self.acct()}, {"id": TID, "time": "x", "amount": TIYIN, "account": self.acct()},
                  {"id": 5, "time": 1, "amount": TIYIN, "account": self.acct()}):
            self.assertEqual(rpc("CreateTransaction", p)[1]["error"]["code"], -32600)

    def test_database_makes_provider_ids_unique(self):
        self.create()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Tx.objects.create(provider="payme", external_id=TID, order_id=self.oid, amount_minor=5, created_ms=1, status="cancelled")

    def test_expired_transaction_is_cancelled_and_refused(self):
        self.create()
        Tx.objects.update(created_ms=1)                                   # created long ago
        st, body = self.create()
        self.assertEqual(body["error"]["code"], -31008)
        t = Tx.objects.get()
        self.assertEqual((t.status, t.reason), ("cancelled", 4))          # the cancellation was committed, not rolled back


class PerformTests(Base):
    def test_pays_the_order_once(self):
        self.create()
        st, body = self.perform()
        self.assertEqual(body["result"]["state"], 2)
        o = self.order()
        self.assertEqual((o.paid_amount, o.payment_status), (Decimal(SUM), "paid"))
        p = OrderPayment.objects.get()
        self.assertEqual((p.status, p.method, p.kind, p.amount, p.created_by_id), ("confirmed", "provider", "payment", Decimal(SUM), None))
        self.assertTrue(Notification.objects.filter(user=self.user).exists())
        self.assertTrue(AuditLog.objects.filter(event="payment.provider_performed").exists())
        self.assertTrue(AuditLog.objects.filter(event="payment.payment_provider").exists())

    def test_retry_returns_the_same_answer_and_moves_no_more_money(self):
        self.create()
        first = self.perform()[1]["result"]
        second = self.perform()[1]["result"]
        self.assertEqual(first, second)
        self.assertEqual(OrderPayment.objects.count(), 1)
        self.assertEqual(self.order().paid_amount, Decimal(SUM))

    def test_unknown_transaction(self):
        self.assertEqual(self.perform("nope")[1]["error"]["code"], -31003)

    def test_cannot_perform_a_cancelled_transaction(self):
        self.create()
        rpc("CancelTransaction", {"id": TID, "reason": 3})
        self.assertEqual(self.perform()[1]["error"]["code"], -31008)
        self.assertEqual(OrderPayment.objects.count(), 0)

    def test_expired_transaction_is_not_performed(self):
        self.create()
        Tx.objects.update(created_ms=1)
        self.assertEqual(self.perform()[1]["error"]["code"], -31008)
        t = Tx.objects.get()
        self.assertEqual((t.status, t.reason), ("cancelled", 4))
        self.assertEqual(OrderPayment.objects.count(), 0)

    def test_order_no_longer_payable_is_refused_without_side_effects(self):
        self.create()
        Order.objects.filter(pk=self.oid).update(status="cancelled")
        self.assertEqual(self.perform()[1]["error"]["code"], -31008)
        self.assertEqual((Tx.objects.get().status, OrderPayment.objects.count()), ("created", 0))

    def test_a_paid_order_takes_no_second_invoice(self):
        self.create()
        self.perform()
        self.assertEqual(self.create(tid=TID2)[1]["error"]["code"], -31051)


class CancelTests(Base):
    def test_cancel_before_payment(self):
        self.create()
        st, body = rpc("CancelTransaction", {"id": TID, "reason": 4})
        self.assertEqual(body["result"]["state"], -1)
        self.assertEqual(Tx.objects.get().reason, 4)
        self.assertEqual(self.create(tid=TID2)[0], 200)                    # the order can be invoiced again

    def test_refund_after_payment(self):
        self.create()
        self.perform()
        st, body = rpc("CancelTransaction", {"id": TID, "reason": 5})
        self.assertEqual(body["result"]["state"], -2)
        o = self.order()
        self.assertEqual(o.payment_status, "refunded")
        kinds = sorted(OrderPayment.objects.values_list("kind", "status", "method"))
        self.assertEqual(kinds, [("payment", "confirmed", "provider"), ("refund", "confirmed", "provider")])
        self.assertTrue(AuditLog.objects.filter(event="payment.provider_refunded").exists())

    def test_cancel_is_idempotent(self):
        self.create()
        self.perform()
        a = rpc("CancelTransaction", {"id": TID, "reason": 5})[1]["result"]
        b = rpc("CancelTransaction", {"id": TID, "reason": 5})[1]["result"]
        self.assertEqual(a, b)
        self.assertEqual(OrderPayment.objects.filter(kind="refund").count(), 1)

    def test_delivered_orders_cannot_be_cancelled(self):
        self.create()
        self.perform()
        Order.objects.filter(pk=self.oid).update(status="delivered")
        self.assertEqual(rpc("CancelTransaction", {"id": TID, "reason": 5})[1]["error"]["code"], -31007)
        self.assertEqual((Tx.objects.get().status, OrderPayment.objects.filter(kind="refund").count()), ("performed", 0))

    def test_unknown_and_bad_params(self):
        self.assertEqual(rpc("CancelTransaction", {"id": "nope", "reason": 1})[1]["error"]["code"], -31003)
        self.assertEqual(rpc("CancelTransaction", {"id": TID})[1]["error"]["code"], -32600)


class CheckAndStatementTests(Base):
    def test_check_transaction_lifecycle(self):
        self.assertEqual(rpc("CheckTransaction", {"id": TID})[1]["error"]["code"], -31003)
        self.create()
        r = rpc("CheckTransaction", {"id": TID})[1]["result"]
        self.assertEqual((r["state"], r["perform_time"], r["cancel_time"], r["reason"]), (1, 0, 0, None))
        self.perform()
        r = rpc("CheckTransaction", {"id": TID})[1]["result"]
        self.assertEqual(r["state"], 2)
        self.assertGreater(r["perform_time"], 0)

    def test_statement_window_and_fields(self):
        self.create(t=1000)
        rpc("CancelTransaction", {"id": TID, "reason": 4})
        self.create(tid=TID2, t=5000)
        rows = rpc("GetStatement", {"from": 0, "to": 10_000})[1]["result"]["transactions"]
        self.assertEqual([r["id"] for r in rows], [TID, TID2])
        self.assertEqual((rows[0]["time"], rows[0]["amount"], rows[0]["account"], rows[0]["state"], rows[0]["receivers"]), (1000, TIYIN, {"order_id": self.num}, -1, None))
        self.assertEqual([r["id"] for r in rpc("GetStatement", {"from": 2000, "to": 10_000})[1]["result"]["transactions"]], [TID2])
        self.assertEqual(rpc("GetStatement", {"from": 20_000, "to": 30_000})[1]["result"], {"transactions": []})
        self.assertEqual(rpc("GetStatement", {"from": "a", "to": 1})[1]["error"]["code"], -32600)


class IsolationTests(Base):
    def test_one_order_cannot_be_paid_through_another(self):
        other = shop("Beta", "b@x.com")
        r = self.c.post("/api/v1/marketplace/orders/", {"workshop": other.pk, "furniture": FURN}, format="json")
        from apps.core.tests.helpers import client_for
        client_for(other.owner).patch(f"/api/v1/orders/{r.data['id']}/", {"status": "confirmed"}, format="json")
        o2 = Order.objects.get(pk=r.data["id"])
        Order.objects.filter(pk=o2.pk).update(total_price=Decimal("500000"), quote={**o2.quote, "currency": "UZS"})
        self.create()
        # the first invoice is for order 1 and only its own amount; order 2 stays unpaid
        self.perform()
        self.assertEqual(Order.objects.get(pk=o2.pk).paid_amount, 0)
        self.assertEqual(rpc("CheckPerformTransaction", {"amount": TIYIN, "account": {"order_id": o2.order_number}})[1]["error"]["code"], -31001)
