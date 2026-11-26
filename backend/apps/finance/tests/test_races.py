"""Money and reminders under concurrency (PostgreSQL only: SQLite serialises writers and would prove nothing)."""
import datetime
from decimal import Decimal
from unittest import skipUnless

from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone

from apps.core.tests.helpers import client_for, make_user
from apps.marketplace import tasks
from apps.marketplace.tests.helpers import FURN, customer, shop
from apps.notifications.models import Notification
from apps.workshops.models import Order
from apps.workshops.tests.test_concurrency import run_together

M = "/api/v1/marketplace/"
POSTGRES = connection.vendor == "postgresql"


@skipUnless(POSTGRES, "needs concurrent PostgreSQL connections")
class MoneyRaceTests(TransactionTestCase):
    def _fixture_teardown(self):
        with connection.cursor() as c:
            c.execute("ALTER TABLE audit_auditlog DISABLE TRIGGER USER")
        try:
            super()._fixture_teardown()
        finally:
            with connection.cursor() as c:
                c.execute("ALTER TABLE audit_auditlog ENABLE TRIGGER USER")

    def setUp(self):
        self.ws = shop("Alpha", "a@x.com")
        self.user, self.c = customer()
        self.admin = make_user("adm@x.com", "maker", is_staff=True)
        r = self.c.post(M + "orders/", {"workshop": self.ws.pk, "furniture": FURN}, format="json")
        self.oid, self.total = r.data["id"], Decimal(r.data["total_price"])
        client_for(self.ws.owner).patch(f"/api/v1/orders/{self.oid}/", {"status": "confirmed"}, format="json")

    def test_the_same_payment_confirmed_twice_at_once_is_counted_once(self):
        pid = self.c.post(f"{M}orders/{self.oid}/payments/", {"amount": "10.00"}, format="json").data["id"]
        url = f"/api/v1/admin-api/finance/payments/{pid}/confirm/"
        res = run_together([lambda: client_for(self.admin).post(url).status_code for _ in range(4)])
        self.assertEqual(sorted(res), [200, 400, 400, 400])
        self.assertEqual(Order.objects.get(pk=self.oid).paid_amount, Decimal("10.00"))

    def test_many_retries_with_one_idempotency_key_record_one_payment(self):
        res = run_together([lambda: self.c.post(f"{M}orders/{self.oid}/payments/", {"amount": "5.00", "idempotency_key": "same"}, format="json").status_code
                            for _ in range(5)])
        self.assertEqual(sorted(res).count(201), 1)
        from apps.finance.models import OrderPayment
        self.assertEqual(OrderPayment.objects.count(), 1)

    def test_two_workers_never_send_the_same_reminder_twice(self):
        Order.objects.filter(pk=self.oid).update(status="pending", responded_at=None, created_at=timezone.now() - datetime.timedelta(hours=5))
        sent = run_together([tasks.send_reminders for _ in range(4)])
        self.assertEqual(sum(sent), 1)
        self.assertEqual(Order.objects.get(pk=self.oid).reminders_sent, 1)
        self.assertEqual(Notification.objects.filter(user=self.ws.owner, title__startswith="Reminder").count(), 1)
