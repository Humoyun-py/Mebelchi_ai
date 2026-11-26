"""Races and rollbacks. The races need real concurrent database connections, so they run on PostgreSQL only (SQLite serialises writers
and would prove nothing); the rollback tests run on every database."""
import threading
from unittest import mock, skipUnless

from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase

from apps.audit.models import AuditLog
from apps.core.tests.helpers import client_for, make_user
from apps.notifications.models import Notification
from apps.workshops import services
from apps.workshops.models import Order, Workshop, WorkshopMember

from .helpers import API, ORDERS, WS, add_member, make_workshop, member_of

M = WorkshopMember
POSTGRES = connection.vendor == "postgresql"


def run_together(jobs):
    """Runs every callable in its own thread (own DB connection) released at the same moment; returns results in order."""
    barrier, results = threading.Barrier(len(jobs)), [None] * len(jobs)

    def go(i, job):
        try:
            barrier.wait(timeout=10)
            results[i] = job()
        except Exception as e:  # noqa: BLE001 - the test inspects what happened
            results[i] = e
        finally:
            close_old_connections()
            connection.close()

    threads = [threading.Thread(target=go, args=(i, j)) for i, j in enumerate(jobs)]
    [t.start() for t in threads]
    [t.join(30) for t in threads]
    return results


@skipUnless(POSTGRES, "needs concurrent PostgreSQL connections")
class RaceTests(TransactionTestCase):
    # The race tests commit for real, so Django empties the tables afterwards with TRUNCATE, which the append-only trigger (rightly)
    # refuses. The trigger is switched off for that one flush, in the throwaway test database only, and switched back on right after.
    serialized_rollback = True

    def _fixture_teardown(self):
        with connection.cursor() as c:
            c.execute("ALTER TABLE audit_auditlog DISABLE TRIGGER USER")
        try:
            super()._fixture_teardown()
        finally:
            with connection.cursor() as c:
                c.execute("ALTER TABLE audit_auditlog ENABLE TRIGGER USER")

    def test_parallel_order_creation_gives_every_order_its_own_number(self):
        owner = make_user("o@x.com", "maker")
        ws = make_workshop(owner)
        def create(i):
            return lambda: client_for(owner).post(ORDERS, {"workshop": ws.pk, "title": f"Order {i}", "customer_name": "Ali"}, format="json")
        results = run_together([create(i) for i in range(10)])
        self.assertTrue(all(not isinstance(r, Exception) and r.status_code == 201 for r in results), [getattr(r, "status_code", r) for r in results])
        numbers = list(Order.objects.filter(workshop=ws).values_list("order_number", flat=True))
        self.assertEqual(len(numbers), 10)
        self.assertEqual(len(set(numbers)), 10)
        ws.refresh_from_db()
        self.assertEqual(ws.order_counter, 10)
        self.assertEqual(sorted(numbers)[-1], f"ORD-{ws.pk:04d}-{10:06d}")

    def test_two_simultaneous_ownership_transfers_leave_exactly_one_owner(self):
        owner = make_user("o@x.com", "maker")
        e1, e2 = make_user("e1@x.com", "maker"), make_user("e2@x.com", "maker")
        ws = make_workshop(owner)
        m1, m2 = add_member(ws, e1), add_member(ws, e2)
        def transfer(m):
            return lambda: client_for(owner).patch(f"{WS}{ws.pk}/members/{m.pk}/", {"role": "owner", "confirm_transfer": True}, format="json")
        results = run_together([transfer(m1), transfer(m2)])
        codes = sorted(getattr(r, "status_code", 599) for r in results)
        self.assertNotIn(599, codes, results)
        self.assertLess(max(codes), 500, codes)
        self.assertEqual(codes.count(200), 1, codes)                       # the loser finds they are no longer the owner
        owners = list(M.objects.filter(workshop=ws, role="owner"))
        self.assertEqual(len(owners), 1)
        ws.refresh_from_db()
        self.assertEqual(ws.owner_id, owners[0].user_id)
        self.assertEqual(M.objects.filter(workshop=ws, status="active").count(), 3)    # nobody lost their membership

    def test_inviting_the_same_person_twice_at_once_creates_one_invitation(self):
        owner, guest = make_user("o@x.com", "maker"), make_user("g@x.com", "maker")
        ws = make_workshop(owner)
        job = lambda: client_for(owner).post(f"{WS}{ws.pk}/members/", {"email": "g@x.com"}, format="json")
        results = run_together([job, job, job])
        codes = sorted(getattr(r, "status_code", 599) for r in results)
        self.assertEqual(codes.count(201), 1, (codes, [r for r in results if isinstance(r, Exception)]))
        self.assertLess(max(codes), 500, codes)
        self.assertEqual(M.objects.filter(workshop=ws, user=guest).count(), 1)

    def test_two_administrators_rejecting_at_once_apply_one_decision(self):
        ws = make_workshop(make_user("o@x.com", "maker"), approve=False)
        admin = make_user("a@x.com", "homeowner", is_staff=True)
        job = lambda: client_for(admin).post(f"{API}admin-api/workshops/{ws.pk}/reject/", {"note": "no"}, format="json")
        codes = sorted(getattr(r, "status_code", 599) for r in run_together([job, job]))
        self.assertEqual(codes, [200, 400], codes)
        self.assertEqual(AuditLog.objects.filter(event="workshop.rejected").count(), 1)
        self.assertEqual(Notification.objects.filter(user=ws.owner, title="Your workshop application was rejected").count(), 1)

    def test_approve_and_reject_at_once_end_in_a_consistent_state(self):
        # Either order is legitimate (a rejected application may be approved afterwards), but never a lost or doubled decision.
        ws = make_workshop(make_user("o@x.com", "maker"), approve=False)
        admin = make_user("a@x.com", "homeowner", is_staff=True)
        url = f"{API}admin-api/workshops/{ws.pk}/"
        results = run_together([lambda: client_for(admin).post(url + "approve/", {}, format="json"),
                                lambda: client_for(admin).post(url + "reject/", {"note": "no"}, format="json")])
        codes = [getattr(r, "status_code", 599) for r in results]
        self.assertLess(max(codes), 500, codes)
        events = list(AuditLog.objects.filter(model="workshops.workshop", event__in=["workshop.approved", "workshop.rejected"]).order_by("id").values_list("event", flat=True))
        self.assertIn(events, (["workshop.approved"], ["workshop.rejected", "workshop.approved"]), events)
        self.assertEqual(Workshop.objects.get(pk=ws.pk).status, "active")        # approval always wins: it is allowed after a rejection, rejection is not allowed after it
        self.assertEqual(sum(c == 200 for c in codes), len(events))              # every 200 left exactly one audit row


class RollbackTests(TestCase):
    def setUp(self):
        self.owner, self.e1 = make_user("o@x.com", "maker"), make_user("e1@x.com", "maker")
        self.ws = make_workshop(self.owner)

    def test_a_failure_while_creating_an_order_leaves_no_order_no_number_and_no_audit_row(self):
        audit_before = AuditLog.objects.count()
        with mock.patch.object(services, "_log_order", side_effect=RuntimeError("history write failed")):
            with self.assertRaises(RuntimeError):
                services.create_order(self.ws, self.owner, {"title": "Kitchen", "customer_name": "Ali"})
        self.assertEqual(Order.objects.count(), 0)
        self.ws.refresh_from_db()
        self.assertEqual(self.ws.order_counter, 0)                       # the number was not burned
        self.assertEqual(AuditLog.objects.count(), audit_before)         # the audit row of the failed attempt was rolled back too
        order = services.create_order(self.ws, self.owner, {"title": "Kitchen", "customer_name": "Ali"})
        self.assertTrue(order.order_number.endswith("-000001"))

    def test_a_failure_halfway_through_an_ownership_transfer_changes_nothing(self):
        add_member(self.ws, self.e1)
        target = member_of(self.ws, self.e1)
        real, calls = services.save_with_event, []
        def flaky(obj, event, *a, **kw):
            calls.append(event)
            if len(calls) == 3:
                raise RuntimeError("audit write failed")
            return real(obj, event, *a, **kw)
        with mock.patch.object(services, "save_with_event", side_effect=flaky):
            with self.assertRaises(RuntimeError):
                services.transfer_ownership(self.ws, self.owner, target)
        self.assertEqual(calls, ["member.role_changed", "member.role_changed", "workshop.owner_changed"])
        self.assertEqual(list(M.objects.filter(workshop=self.ws, role="owner").values_list("user_id", flat=True)), [self.owner.pk])
        self.ws.refresh_from_db()
        self.assertEqual(self.ws.owner_id, self.owner.pk)
        self.assertEqual(AuditLog.objects.filter(event__in=["member.role_changed", "workshop.owner_changed"]).count(), 0)

    def test_a_failed_review_changes_neither_the_status_nor_notifies_the_owner(self):
        ws = make_workshop(make_user("p@x.com", "maker"), "Pending", approve=False)
        admin = make_user("a@x.com", "homeowner", is_staff=True)
        with mock.patch.object(services, "save_with_event", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                services.review_workshop(ws, admin, Workshop.Status.ACTIVE)
        self.assertEqual(Workshop.objects.get(pk=ws.pk).status, "pending")
        self.assertFalse(Notification.objects.filter(user=ws.owner, title="Your workshop was approved").exists())
