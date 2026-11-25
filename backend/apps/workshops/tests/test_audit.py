from django.test import TestCase

from apps.audit.models import AuditLog
from apps.core.tests.helpers import client_for, make_user
from apps.workshops.models import Order

from .helpers import API, ORDERS, TASKS, WS, Scene, hours, make_order, make_task, make_workshop

ADMIN = API + "admin-api/audit-logs/"


def events(**kw):
    return list(AuditLog.objects.filter(**kw).exclude(event="").order_by("id").values_list("event", flat=True))


class WorkshopAuditTests(TestCase):
    def test_workshop_and_member_events(self):
        owner, emp = make_user("o@x.com", "maker"), make_user("e@x.com", "maker")
        c = client_for(owner)
        ws = make_workshop(owner, "Audit Shop")
        self.assertEqual(events(model="workshops.workshop"), ["workshop.created"])
        c.patch(f"{WS}{ws.pk}/", {"description": "new text"}, format="json")
        self.assertEqual(events(model="workshops.workshop")[-1], "workshop.updated")
        mid = c.post(f"{WS}{ws.pk}/members/", {"email": "e@x.com"}, format="json").data["id"]
        client_for(emp).patch(f"{WS}{ws.pk}/members/{mid}/", {"status": "active"}, format="json")
        c.patch(f"{WS}{ws.pk}/members/{mid}/", {"role": "owner", "confirm_transfer": True}, format="json")
        self.assertEqual(events(model="workshops.workshopmember"), ["member.invited", "member.accepted", "member.role_changed", "member.role_changed"])
        client_for(emp).delete(f"{WS}{ws.pk}/members/{mid}/")  # emp is now the owner: cannot remove self
        c2 = client_for(emp)
        other = make_user("x@x.com", "maker")
        oid = c2.post(f"{WS}{ws.pk}/members/", {"email": "x@x.com"}, format="json").data["id"]
        c2.delete(f"{WS}{ws.pk}/members/{oid}/")
        self.assertEqual(events(model="workshops.workshopmember")[-2:], ["member.invited", "member.removed"])
        self.assertIn("workshop.owner_changed", events(model="workshops.workshop"))

    def test_entries_carry_actor_ip_object_and_changes(self):
        owner = make_user("o@x.com", "maker")
        ws = make_workshop(owner)
        AuditLog.objects.all().delete()
        client_for(owner).patch(f"{WS}{ws.pk}/", {"phone": "+998 90 000 00 00"}, format="json", REMOTE_ADDR="203.0.113.5")
        e = AuditLog.objects.get(model="workshops.workshop")
        self.assertEqual((e.actor, e.action, e.event, e.object_id, e.object_repr, e.ip, e.method), (owner, "update", "workshop.updated", str(ws.pk), "Alpha Workshop", "203.0.113.5", "PATCH"))
        self.assertEqual(e.changes["phone"], {"old": "", "new": "+998 90 000 00 00"})

    def test_a_denied_action_leaves_no_trace(self):
        s = Scene()
        AuditLog.objects.all().delete()
        s.c_emp1.patch(f"{WS}{s.ws.pk}/", {"name": "Hijack"}, format="json")
        s.c_emp1.post(f"{WS}{s.ws.pk}/members/", {"email": s.stranger.email}, format="json")
        self.assertEqual(AuditLog.objects.count(), 0)


class OrderAuditTests(TestCase):
    def setUp(self):
        self.s = Scene()
        AuditLog.objects.all().delete()

    def test_order_events(self):
        o = make_order(self.s.ws, self.s.owner, total_price="100")
        self.s.c_owner.patch(f"{ORDERS}{o.pk}/", {"title": "Renamed"}, format="json")
        self.s.c_owner.patch(f"{ORDERS}{o.pk}/", {"status": "confirmed", "paid_amount": "40"}, format="json")
        self.assertEqual(events(model="workshops.order"), ["order.created", "order.updated", "order.status_changed"])
        change = AuditLog.objects.get(event="order.status_changed")
        self.assertEqual(change.changes["status"], {"old": "new", "new": "confirmed"})
        self.assertEqual(change.changes["paid_amount"], {"old": "0.00", "new": "40.00"})
        self.assertEqual(change.changes["payment_status"], {"old": "unpaid", "new": "partially_paid"})
        self.assertEqual((change.actor, change.object_repr), (self.s.owner, o.order_number))

    def test_order_delete_is_recorded(self):
        o = make_order(self.s.ws, self.s.owner)
        self.s.c_owner.delete(f"{ORDERS}{o.pk}/")
        self.assertEqual(events(model="workshops.order"), ["order.created", "order.deleted"])

    def test_customer_contact_details_are_never_written_to_the_log(self):
        o = make_order(self.s.ws, self.s.owner, customer_phone="+998901234567", customer_email="ali@secret.example", customer_address="Secret street 1")
        self.s.c_owner.patch(f"{ORDERS}{o.pk}/", {"customer_phone": "+998909999999", "customer_email": "new@secret.example"}, format="json")
        dump = str(list(AuditLog.objects.values("changes", "object_repr")))
        for secret in ("998901234567", "998909999999", "secret.example", "Secret street"):
            self.assertNotIn(secret, dump)
        e = AuditLog.objects.get(event="order.updated")
        self.assertEqual(e.changes["customer_phone"], {"old": "[redacted]", "new": "[redacted]"})
        self.assertEqual(e.changes["customer_email"], {"old": "[redacted]", "new": "[redacted]"})

    def test_no_tokens_or_passwords_in_workshop_events(self):
        make_order(self.s.ws, self.s.owner)
        dump = str(list(AuditLog.objects.values_list("changes", flat=True))).lower()
        for word in ("pbkdf2", "bearer", "eyj"):
            self.assertNotIn(word, dump)

    def test_status_history_is_not_a_second_audit_stream_but_cancel_cascades_are_visible(self):
        o = make_order(self.s.ws, self.s.owner)
        make_task(self.s.owner, o)
        AuditLog.objects.all().delete()
        self.s.c_owner.patch(f"{ORDERS}{o.pk}/", {"status": "cancelled"}, format="json")
        self.assertEqual(events(), ["order.status_changed", "task.status_changed"])


class TaskAuditTests(TestCase):
    def setUp(self):
        self.s = Scene()
        self.order = make_order(self.s.ws, self.s.owner)
        AuditLog.objects.all().delete()

    def test_task_events(self):
        t = make_task(self.s.owner, self.order, assigned_to=self.s.m_emp1.pk, deadline=hours(5).isoformat())
        self.s.c_owner.patch(f"{TASKS}{t.pk}/", {"assigned_to": self.s.m_emp2.pk}, format="json")
        self.s.c_emp2.patch(f"{TASKS}{t.pk}/", {"status": "in_progress"}, format="json")
        self.s.c_emp2.patch(f"{TASKS}{t.pk}/", {"status": "review"}, format="json")
        self.s.c_owner.patch(f"{TASKS}{t.pk}/", {"priority": "urgent"}, format="json")
        self.s.c_owner.patch(f"{TASKS}{t.pk}/", {"status": "completed"}, format="json")
        self.assertEqual(events(model="workshops.task"), ["task.created", "task.assigned", "task.status_changed", "task.status_changed", "task.updated",
                                                          "task.completed"])
        assigned = AuditLog.objects.get(event="task.assigned")
        self.assertEqual(assigned.changes["assigned_to"], {"old": self.s.m_emp1.pk, "new": self.s.m_emp2.pk})
        status = AuditLog.objects.filter(event="task.status_changed").order_by("id").first()
        self.assertEqual((status.actor, status.changes["status"]), (self.s.emp2, {"old": "pending", "new": "in_progress"}))
        self.assertEqual(AuditLog.objects.get(event="task.completed").actor, self.s.owner)

    def test_an_employees_denied_edit_is_not_logged(self):
        t = make_task(self.s.owner, self.order, assigned_to=self.s.m_emp1.pk)
        AuditLog.objects.all().delete()
        self.s.c_emp1.patch(f"{TASKS}{t.pk}/", {"title": "x"}, format="json")
        self.s.c_emp1.patch(f"{TASKS}{t.pk}/", {"status": "completed"}, format="json")
        self.assertEqual(AuditLog.objects.count(), 0)


class AdminAuditViewTests(TestCase):
    def test_admins_can_filter_the_workshop_events_and_nobody_else_can_read_them(self):
        s = Scene()
        o = make_order(s.ws, s.owner)
        s.c_owner.patch(f"{ORDERS}{o.pk}/", {"status": "confirmed"}, format="json")
        admin = client_for(make_user("admin@x.com", "maker", is_staff=True))
        r = admin.get(ADMIN, {"event": "order.status_changed"})
        self.assertEqual((r.status_code, r.data["count"], r.data["results"][0]["event"]), (200, 1, "order.status_changed"))
        self.assertEqual(admin.get(ADMIN, {"model": "workshops.order", "object_id": o.pk}).data["count"], 2)
        for c in (s.c_owner, s.c_emp1, client_for()):
            self.assertIn(c.get(ADMIN).status_code, (401, 403))


class MemberLabelTests(TestCase):
    def test_audit_label_of_a_member_is_readable_and_costs_no_query(self):
        from apps.workshops.models import WorkshopMember
        s = Scene()
        m = WorkshopMember.objects.get(pk=s.m_emp1.pk)               # relations not loaded
        with self.assertNumQueries(0):
            self.assertEqual(str(m), f"user {s.emp1.pk} in workshop {s.ws.pk} (employee)")
        m = WorkshopMember.objects.select_related("user", "workshop").get(pk=s.m_emp1.pk)
        with self.assertNumQueries(0):
            self.assertEqual(str(m), "emp1@a.com in Alpha Workshop (employee)")

    def test_invited_member_event_names_the_person_and_workshop(self):
        s = Scene()
        AuditLog.objects.all().delete()
        s.c_owner.post(f"{WS}{s.ws.pk}/members/", {"email": s.stranger.email}, format="json")
        self.assertEqual(AuditLog.objects.get(event="member.invited").object_repr, "stranger@x.com in Alpha Workshop (employee)")
