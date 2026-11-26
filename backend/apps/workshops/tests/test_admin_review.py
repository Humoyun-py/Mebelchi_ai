"""Platform administrators review workshop applications (Phase 4.7): approve, reject with a reason, suspend, reactivate; assign the
Workshop role; read the history. Every rule is enforced by the API, not by the UI."""
from django.test import TestCase

from apps.audit.models import AuditLog
from apps.core.tests.helpers import client_for, make_user
from apps.notifications.models import Notification
from apps.workshops.models import Workshop

from .helpers import API, WS, make_workshop

ADMIN_WS = API + "admin-api/workshops/"
ADMIN_USERS = API + "admin-api/users/"
AUDIT = API + "admin-api/audit-logs/"


def staff():
    return make_user("admin@x.com", "homeowner", is_staff=True)


def pending_workshop(email="o@x.com", name="Pending Shop"):
    return make_workshop(make_user(email, "maker"), name, approve=False)


class ReviewPermissionTests(TestCase):
    def setUp(self):
        self.ws = pending_workshop()

    def test_only_platform_administrators_may_review(self):
        for who in (None, make_user("home@x.com", "homeowner"), make_user("mk@x.com", "maker"), self.ws.owner):
            c = client_for(who)
            for action in ("approve", "reject", "suspend"):
                r = c.post(f"{ADMIN_WS}{self.ws.pk}/{action}/", {"note": "x"}, format="json")
                self.assertIn(r.status_code, (401, 403), f"{who} {action}")
        self.assertEqual(Workshop.objects.get().status, "pending")
        self.assertFalse(AuditLog.objects.filter(event__startswith="workshop.").exclude(event="workshop.created").exists())

    def test_the_list_is_closed_to_everyone_else(self):
        self.assertEqual(client_for(self.ws.owner).get(ADMIN_WS).status_code, 403)
        self.assertEqual(client_for().get(ADMIN_WS).status_code, 401)

    def test_an_owner_cannot_approve_their_own_workshop_through_the_normal_api(self):
        r = client_for(self.ws.owner).patch(f"{WS}{self.ws.pk}/", {"status": "active"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(Workshop.objects.get().status, "pending")

    def test_staff_has_no_access_to_workshop_data_through_the_member_api(self):
        self.assertEqual(client_for(staff()).get(f"{WS}{self.ws.pk}/").status_code, 404)


class ReviewFlowTests(TestCase):
    def setUp(self):
        self.admin = client_for(staff())
        self.ws = pending_workshop()
        self.url = f"{ADMIN_WS}{self.ws.pk}/"

    def status(self):
        return Workshop.objects.get(pk=self.ws.pk).status

    def test_pending_filter_and_search(self):
        other = make_workshop(make_user("a@x.com", "maker"), "Active One")
        r = self.admin.get(ADMIN_WS, {"status": "pending"})
        self.assertEqual([w["id"] for w in r.data["results"]], [self.ws.pk])
        self.assertEqual(r.data["results"][0]["owner_email"], "o@x.com")
        self.assertEqual(self.admin.get(ADMIN_WS, {"search": "Active"}).data["results"][0]["id"], other.pk)

    def test_approve_activates_notifies_and_audits(self):
        r = self.admin.post(self.url + "approve/", {}, format="json")
        self.assertEqual((r.status_code, r.data["status"]), (200, "active"))
        self.assertEqual(self.status(), "active")
        self.assertTrue(Notification.objects.filter(user=self.ws.owner, title="Your workshop was approved").exists())
        e = AuditLog.objects.get(event="workshop.approved")
        self.assertEqual((e.model, e.object_id, e.actor_email), ("workshops.workshop", str(self.ws.pk), "admin@x.com"))
        self.assertEqual(e.changes["status"], {"old": "pending", "new": "active"})

    def test_reject_needs_a_reason_and_keeps_it(self):
        for body in ({}, {"note": ""}, {"note": "   "}):
            r = self.admin.post(self.url + "reject/", body, format="json")
            self.assertEqual(r.status_code, 400, body)
        self.assertEqual(self.status(), "pending")
        r = self.admin.post(self.url + "reject/", {"note": "Phone number does not work"}, format="json")
        self.assertEqual((r.status_code, r.data["status"], r.data["review_note"]), (200, "rejected", "Phone number does not work"))
        ws = Workshop.objects.get(pk=self.ws.pk)
        self.assertEqual((ws.status, ws.review_note), ("rejected", "Phone number does not work"))
        e = AuditLog.objects.get(event="workshop.rejected")
        self.assertEqual(e.changes["status"], {"old": "pending", "new": "rejected"})
        self.assertEqual(e.changes["review_note"]["new"], "Phone number does not work")
        n = Notification.objects.get(user=self.ws.owner, title="Your workshop application was rejected")
        self.assertIn("Phone number", n.message if hasattr(n, "message") else n.body)

    def test_the_owner_sees_the_reason_but_cannot_work_or_reopen(self):
        self.admin.post(self.url + "reject/", {"note": "Missing address"}, format="json")
        owner = client_for(self.ws.owner)
        self.assertEqual(owner.get(f"{WS}{self.ws.pk}/").data["review_note"], "Missing address")
        self.assertEqual(owner.patch(f"{WS}{self.ws.pk}/", {"status": "active"}, format="json").status_code, 403)
        self.assertEqual(owner.post(f"{WS}{self.ws.pk}/members/", {"email": "nobody@x.com"}, format="json").status_code, 403)
        self.assertEqual(self.status(), "rejected")

    def test_review_note_cannot_be_forged_by_the_owner(self):
        owner = client_for(self.ws.owner)
        owner.patch(f"{WS}{self.ws.pk}/", {"review_note": "approved by me"}, format="json")
        self.assertEqual(Workshop.objects.get(pk=self.ws.pk).review_note, "")

    def test_only_a_pending_application_can_be_rejected(self):
        self.admin.post(self.url + "approve/", {}, format="json")
        r = self.admin.post(self.url + "reject/", {"note": "too late"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.status(), "active")

    def test_a_rejected_application_can_be_reconsidered(self):
        self.admin.post(self.url + "reject/", {"note": "Missing address"}, format="json")
        r = self.admin.post(self.url + "approve/", {}, format="json")
        self.assertEqual((r.status_code, r.data["status"], r.data["review_note"]), (200, "active", ""))
        self.assertEqual(list(AuditLog.objects.filter(model="workshops.workshop", object_id=str(self.ws.pk)).exclude(event="workshop.created")
                              .order_by("id").values_list("event", flat=True)), ["workshop.rejected", "workshop.approved"])

    def test_suspend_and_reactivate(self):
        self.admin.post(self.url + "approve/", {}, format="json")
        r = self.admin.post(self.url + "suspend/", {"note": "Complaints"}, format="json")
        self.assertEqual((r.data["status"], r.data["review_note"]), ("suspended", "Complaints"))
        self.assertEqual(client_for(self.ws.owner).patch(f"{WS}{self.ws.pk}/", {"description": "x"}, format="json").status_code, 403)
        self.assertEqual(self.admin.post(self.url + "approve/", {}, format="json").data["status"], "active")
        self.assertIn("workshop.reactivated", AuditLog.objects.values_list("event", flat=True))

    def test_a_pending_workshop_cannot_be_suspended_and_the_note_is_bounded(self):
        self.assertEqual(self.admin.post(self.url + "suspend/", {"note": "x"}, format="json").status_code, 400)
        self.assertEqual(self.admin.post(self.url + "reject/", {"note": "x" * 501}, format="json").status_code, 400)
        self.assertEqual(self.status(), "pending")

    def test_deciding_twice_in_a_row_is_refused_not_applied_twice(self):
        self.assertEqual(self.admin.post(self.url + "approve/", {}, format="json").status_code, 200)
        self.assertEqual(self.admin.post(self.url + "approve/", {}, format="json").status_code, 400)
        self.assertEqual(AuditLog.objects.filter(event="workshop.approved").count(), 1)

    def test_failed_decisions_leave_no_audit_row_and_no_notification(self):
        before = (AuditLog.objects.count(), Notification.objects.count())
        self.admin.post(self.url + "reject/", {}, format="json")
        self.admin.post(self.url + "suspend/", {"note": "x"}, format="json")
        self.assertEqual((AuditLog.objects.count(), Notification.objects.count()), before)

    def test_unknown_workshop_is_404(self):
        self.assertEqual(self.admin.post(f"{ADMIN_WS}999999/approve/", {}, format="json").status_code, 404)

    def test_history_is_readable_per_workshop(self):
        self.admin.post(self.url + "reject/", {"note": "Missing address"}, format="json")
        self.admin.post(self.url + "approve/", {}, format="json")
        r = self.admin.get(AUDIT, {"model": "workshops.workshop", "object_id": self.ws.pk})
        self.assertEqual([e["event"] for e in r.data["results"]], ["workshop.approved", "workshop.rejected", "workshop.created"])  # newest first
        self.assertEqual(client_for(self.ws.owner).get(AUDIT).status_code, 403)


class RoleManagementTests(TestCase):
    def setUp(self):
        self.admin = client_for(staff())
        self.user = make_user("u@x.com", "maker")

    def test_administrator_assigns_the_workshop_role_and_it_is_audited(self):
        r = self.admin.patch(f"{ADMIN_USERS}{self.user.pk}/", {"role": "workshop"}, format="json")
        self.assertEqual((r.status_code, r.data["role"]), (200, "workshop"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, "workshop")
        e = AuditLog.objects.get(event="user.role_changed")
        self.assertEqual((e.actor_email, e.object_id), ("admin@x.com", str(self.user.pk)))

    def test_nobody_else_can_assign_roles(self):
        for who in (None, self.user, make_user("o@x.com", "homeowner")):
            r = client_for(who).patch(f"{ADMIN_USERS}{self.user.pk}/", {"role": "workshop"}, format="json")
            self.assertIn(r.status_code, (401, 403))
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, "maker")

    def test_a_user_cannot_pick_the_workshop_role_themselves(self):
        r = client_for(self.user).post(API + "auth/role/", {"role": "workshop"}, format="json")
        self.assertIn(r.status_code, (400, 403, 404))
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, "maker")

    def test_invalid_role_is_rejected(self):
        self.assertEqual(self.admin.patch(f"{ADMIN_USERS}{self.user.pk}/", {"role": "superhero"}, format="json").status_code, 400)

    def test_the_assigned_role_allows_creating_a_workshop_that_starts_pending(self):
        self.admin.patch(f"{ADMIN_USERS}{self.user.pk}/", {"role": "workshop"}, format="json")
        self.user.refresh_from_db()
        r = client_for(self.user).post(WS, {"name": "New Shop"}, format="json")
        self.assertEqual((r.status_code, r.data["status"]), (201, "pending"))
