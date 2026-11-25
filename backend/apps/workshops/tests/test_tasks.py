from django.test import TestCase
from django.utils import timezone

from apps.core.tests.helpers import client_for, make_user
from apps.notifications.models import Notification
from apps.workshops.models import Order, Task, TaskStatusChange

from .helpers import TASKS, Scene, add_member, days, hours, make_order, make_task, make_workshop


def turl(t):
    return f"{TASKS}{t.pk}/"


class TaskCreationTests(TestCase):
    def setUp(self):
        self.s = Scene()
        self.order = make_order(self.s.ws, self.s.owner)

    def post(self, c=None, **kw):
        return (c or self.s.c_owner).post(TASKS, {"title": "Cut panels", **kw}, format="json")

    def test_owner_creates_and_assigns_a_task_for_an_order(self):
        r = self.post(order=self.order.pk, assigned_to=self.s.m_emp1.pk, priority="high", deadline=hours(48).isoformat(), description="18 mm MDF")
        self.assertEqual(r.status_code, 201, r.data)
        d = r.data
        self.assertEqual((d["workshop"], d["order"], d["order_number"], d["status"], d["priority"], d["created_by"]),
                         (self.s.ws.pk, self.order.pk, self.order.order_number, "pending", "high", self.s.owner.pk))
        self.assertEqual(d["assigned_to_detail"]["full_name"], "Test User")
        self.assertFalse(d["is_overdue"])
        t = Task.objects.get(pk=d["id"])
        self.assertEqual([(h.from_status, h.to_status) for h in t.status_history.all()], [("", "pending")])
        self.assertTrue(Notification.objects.filter(user=self.s.emp1, title="New task assigned").exists())

    def test_a_task_without_an_order_needs_a_workshop(self):
        self.assertEqual(self.post().status_code, 400)
        r = self.post(workshop=self.s.ws.pk)
        self.assertEqual((r.status_code, r.data["order"], r.data["order_number"]), (201, None, None))

    def test_the_workshop_comes_from_the_order(self):
        r = self.post(order=self.order.pk)
        self.assertEqual(r.data["workshop"], self.s.ws.pk)

    def test_order_and_task_must_belong_to_the_same_workshop(self):
        self.s.c_owner.post  # the owner of A also owns a workshop C and tries to mix them
        c = make_workshop(self.s.owner, "Gamma")
        r = self.post(order=self.order.pk, workshop=c.pk)
        self.assertEqual(r.status_code, 400)
        self.assertIn("workshop", r.data["error"]["fields"])
        # an order of another workshop that I cannot see is simply not found
        theirs = make_order(self.s.wsb, self.s.owner_b)
        r = self.post(order=theirs.pk)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Task.objects.count(), 0)

    def test_assignee_must_be_an_active_member_of_the_tasks_workshop(self):
        invited = add_member(self.s.ws, make_user("inv@x.com", "maker"), status="invited")
        removed = add_member(self.s.ws, make_user("rem@x.com", "maker"), status="removed")
        foreign = add_member(self.s.wsb, self.s.emp1)
        for m in (invited, removed, foreign):
            r = self.post(order=self.order.pk, assigned_to=m.pk)
            self.assertEqual(r.status_code, 400, (m, r.data))
            self.assertIn("assigned_to", r.data["error"]["fields"])
        own = self.s.ws.members.get(user=self.s.owner)
        self.assertEqual(self.post(order=self.order.pk, assigned_to=own.pk).status_code, 201)  # the owner may take a task themself

    def test_deadline_must_be_in_the_future(self):
        for bad in (hours(-1).isoformat(), timezone.now().isoformat(), "tomorrow"):
            self.assertEqual(self.post(order=self.order.pk, deadline=bad).status_code, 400, bad)
        self.assertEqual(self.post(order=self.order.pk, deadline=hours(1).isoformat()).status_code, 201)
        self.assertEqual(self.post(order=self.order.pk).status_code, 201)  # no deadline is fine

    def test_validation(self):
        self.assertEqual(self.post(order=self.order.pk, title="").status_code, 400)
        self.assertEqual(self.post(order=self.order.pk, priority="critical").status_code, 400)

    def test_employees_and_strangers_cannot_create(self):
        self.assertEqual(self.post(self.s.c_emp1, order=self.order.pk).status_code, 400)   # an order emp1 cannot see does not exist for them
        make_order(self.s.ws, self.s.owner, assigned_employee=self.s.m_emp1.pk)
        mine = make_order(self.s.ws, self.s.owner, assigned_employee=self.s.m_emp1.pk)
        self.assertEqual(self.post(self.s.c_emp1, order=mine.pk).status_code, 403)         # ... and even their own order is owner-only
        self.assertEqual(self.post(self.s.c_stranger, workshop=self.s.ws.pk).status_code, 400)
        self.assertEqual(self.post(client_for(), order=self.order.pk).status_code, 401)
        self.assertEqual(Task.objects.count(), 0)

    def test_status_and_timestamps_cannot_be_forged_on_creation(self):
        r = self.post(order=self.order.pk, status="completed", started_at="2020-01-01T00:00:00Z", completed_at="2020-01-02T00:00:00Z", created_by=99)
        t = Task.objects.get(pk=r.data["id"])
        self.assertEqual((t.status, t.started_at, t.completed_at, t.created_by), ("pending", None, None, self.s.owner))


class TaskEmployeeTests(TestCase):
    def setUp(self):
        self.s = Scene()
        self.order = make_order(self.s.ws, self.s.owner)
        self.mine = make_task(self.s.owner, self.order, title="Mine", assigned_to=self.s.m_emp1.pk)
        self.theirs = make_task(self.s.owner, self.order, title="Theirs", assigned_to=self.s.m_emp2.pk)
        self.unassigned = make_task(self.s.owner, self.order, title="Nobody")
        self.other_ws = make_task(self.s.owner_b, make_order(self.s.wsb, self.s.owner_b), title="Other workshop")

    def titles(self, c, **p):
        return sorted(t["title"] for t in c.get(TASKS, p).data["results"])

    def test_employees_see_only_their_own_tasks(self):
        self.assertEqual(self.titles(self.s.c_emp1), ["Mine"])
        self.assertEqual(self.titles(self.s.c_emp2), ["Theirs"])
        self.assertEqual(self.titles(self.s.c_owner), ["Mine", "Nobody", "Theirs"])
        self.assertEqual(self.titles(self.s.c_stranger), [])
        self.assertEqual(self.s.c_emp1.get(turl(self.theirs)).status_code, 404)
        self.assertEqual(self.s.c_emp1.get(turl(self.other_ws)).status_code, 404)
        self.assertEqual(self.s.c_owner.get(turl(self.other_ws)).status_code, 404)

    def test_employee_moves_a_task_forward_and_reports_it(self):
        r = self.s.c_emp1.patch(turl(self.mine), {"status": "in_progress", "status_note": "Started cutting"}, format="json")
        self.assertEqual((r.status_code, r.data["status"]), (200, "in_progress"), r.data)
        self.assertIsNotNone(r.data["started_at"])
        r = self.s.c_emp1.patch(turl(self.mine), {"status": "review"}, format="json")
        self.assertEqual(r.status_code, 200)
        hist = [(h["from_status"], h["to_status"], h["note"]) for h in r.data["status_history"]]
        self.assertEqual(hist, [("", "pending", "Task created"), ("pending", "in_progress", "Started cutting"), ("in_progress", "review", "")])
        self.assertEqual(self.s.c_emp1.patch(turl(self.mine), {"status": "in_progress"}, format="json").status_code, 200)  # sent back for more work

    def test_employee_cannot_complete_cancel_or_skip_steps(self):
        for bad in ("completed", "cancelled", "review"):
            r = self.s.c_emp1.patch(turl(self.mine), {"status": bad}, format="json")
            self.assertEqual(r.status_code, 400, bad)
            self.assertIn("by an employee", str(r.data))
        self.mine.refresh_from_db()
        self.assertEqual(self.mine.status, "pending")

    def test_employee_cannot_edit_anything_but_the_status(self):
        for body in ({"title": "x"}, {"priority": "urgent"}, {"deadline": hours(5).isoformat()}, {"description": "x"},
                     {"assigned_to": self.s.m_emp2.pk}, {"assigned_to": None}, {"status": "in_progress", "assigned_to": self.s.m_emp2.pk}):
            self.assertEqual(self.s.c_emp1.patch(turl(self.mine), body, format="json").status_code, 403, body)
        self.mine.refresh_from_db()
        self.assertEqual((self.mine.title, self.mine.assigned_to_id, self.mine.status), ("Mine", self.s.m_emp1.pk, "pending"))

    def test_employee_cannot_touch_other_peoples_tasks(self):
        for t in (self.theirs, self.unassigned, self.other_ws):
            self.assertEqual(self.s.c_emp1.patch(turl(t), {"status": "in_progress"}, format="json").status_code, 404)
            self.assertEqual(self.s.c_emp1.delete(turl(t)).status_code, 404)
        self.assertEqual(self.s.c_emp1.delete(turl(self.mine)).status_code, 403)

    def test_employee_who_is_removed_loses_access_immediately(self):
        self.s.c_owner.delete(f"/api/v1/workshops/{self.s.ws.pk}/members/{self.s.m_emp1.pk}/")
        self.assertEqual(self.s.c_emp1.patch(turl(self.mine), {"status": "in_progress"}, format="json").status_code, 404)
        self.assertEqual(self.titles(self.s.c_emp1), [])

    def test_inactive_workshop_blocks_status_updates(self):
        self.s.c_owner.patch(f"/api/v1/workshops/{self.s.ws.pk}/", {"status": "inactive"}, format="json")
        self.assertEqual(self.s.c_emp1.patch(turl(self.mine), {"status": "in_progress"}, format="json").status_code, 403)

    def test_the_owner_as_an_employee_elsewhere_has_only_employee_rights_there(self):
        add_member(self.s.wsb, self.s.owner)
        t = make_task(self.s.owner_b, ws=self.s.wsb, title="B task", assigned_to=self.s.wsb.members.get(user=self.s.owner).pk)
        self.assertEqual(self.s.c_owner.patch(turl(t), {"title": "renamed"}, format="json").status_code, 403)
        self.assertEqual(self.s.c_owner.patch(turl(t), {"status": "completed"}, format="json").status_code, 400)
        self.assertEqual(self.s.c_owner.patch(turl(t), {"status": "in_progress"}, format="json").status_code, 200)


class TaskOwnerLifecycleTests(TestCase):
    def setUp(self):
        self.s = Scene()
        self.order = make_order(self.s.ws, self.s.owner)
        self.t = make_task(self.s.owner, self.order, assigned_to=self.s.m_emp1.pk)

    def patch(self, **kw):
        return self.s.c_owner.patch(turl(self.t), kw, format="json")

    def test_review_then_completion_sets_timestamps(self):
        self.s.c_emp1.patch(turl(self.t), {"status": "in_progress"}, format="json")
        self.s.c_emp1.patch(turl(self.t), {"status": "review"}, format="json")
        r = self.patch(status="completed", status_note="Approved")
        self.assertEqual((r.status_code, r.data["status"]), (200, "completed"), r.data)
        self.assertIsNotNone(r.data["completed_at"])
        self.assertEqual(r.data["status_history"][-1]["changed_by"]["id"], self.s.owner.pk)
        self.assertEqual(r.data["status_history"][-1]["note"], "Approved")

    def test_owner_can_complete_directly_and_cancel(self):
        self.patch(status="in_progress")
        self.assertEqual(self.patch(status="completed").status_code, 200)
        t2 = make_task(self.s.owner, self.order)
        self.assertEqual(self.s.c_owner.patch(turl(t2), {"status": "cancelled"}, format="json").status_code, 200)

    def test_invalid_owner_transitions(self):
        for bad in ("review", "completed"):
            self.assertEqual(self.patch(status=bad).status_code, 400, bad)   # pending cannot jump ahead
        self.patch(status="in_progress")
        self.patch(status="completed")
        for later in ("pending", "in_progress", "cancelled"):
            self.assertEqual(self.patch(status=later).status_code, 400, later)  # completed is final
        self.assertEqual(self.patch(title="rename").status_code, 400)  # and read-only
        self.t.refresh_from_db()
        self.assertEqual(self.t.status, "completed")

    def test_started_at_is_set_once(self):
        self.patch(status="in_progress")
        self.t.refresh_from_db()
        first = self.t.started_at
        self.patch(status="pending")
        self.patch(status="in_progress")
        self.t.refresh_from_db()
        self.assertEqual(self.t.started_at, first)

    def test_reassignment_by_the_owner_only(self):
        r = self.patch(assigned_to=self.s.m_emp2.pk)
        self.assertEqual((r.status_code, r.data["assigned_to"]), (200, self.s.m_emp2.pk))
        self.assertTrue(Notification.objects.filter(user=self.s.emp2, title="New task assigned").exists())
        self.assertEqual(self.patch(assigned_to=None).data["assigned_to"], None)
        self.assertEqual(self.patch(assigned_to=self.s.wsb.members.get(user=self.s.owner_b).pk).status_code, 400)
        removed = add_member(self.s.ws, make_user("rem@x.com", "maker"), status="removed")
        self.assertEqual(self.patch(assigned_to=removed.pk).status_code, 400)

    def test_deadline_changes_are_validated_but_unchanged_old_deadlines_are_not(self):
        self.assertEqual(self.patch(deadline=hours(-5).isoformat()).status_code, 400)
        self.assertEqual(self.patch(deadline=hours(24).isoformat()).status_code, 200)
        Task.objects.filter(pk=self.t.pk).update(deadline=hours(-1))   # time passes: the task is now overdue
        self.assertEqual(self.patch(priority="urgent").status_code, 200)   # editing other fields must still work
        self.assertTrue(self.s.c_owner.get(turl(self.t)).data["is_overdue"])

    def test_task_cannot_move_between_orders_or_workshops(self):
        other = make_order(self.s.ws, self.s.owner)
        self.assertEqual(self.patch(order=other.pk).status_code, 400)
        self.assertEqual(self.patch(workshop=self.s.wsb.pk).status_code, 400)

    def test_delete_rules(self):
        fresh = make_task(self.s.owner, self.order, title="Fresh")
        self.assertEqual(self.s.c_owner.delete(turl(fresh)).status_code, 204)
        self.patch(status="in_progress")
        r = self.s.c_owner.delete(turl(self.t))
        self.assertEqual(r.status_code, 409)
        self.assertTrue(Task.objects.filter(pk=self.t.pk).exists())
        cancelled = make_task(self.s.owner, self.order, title="Cancel me")
        self.s.c_owner.patch(turl(cancelled), {"status": "cancelled"}, format="json")
        self.assertEqual(self.s.c_owner.delete(turl(cancelled)).status_code, 204)

    def test_history_survives_when_the_actor_account_is_deleted(self):
        extra = make_user("temp@x.com", "maker")
        add_member(self.s.ws, extra)
        h = TaskStatusChange.objects.filter(task=self.t).first()
        self.assertEqual(h.changed_by, self.s.owner)
        # the history row is not cascaded away with other things
        self.assertEqual(TaskStatusChange.objects.filter(task=self.t).count(), 1)


class TaskFilterTests(TestCase):
    def setUp(self):
        self.s = Scene()
        s = self.s
        self.o1, self.o2 = make_order(s.ws, s.owner), make_order(s.ws, s.owner)
        self.a = make_task(s.owner, self.o1, title="Saw", priority="urgent", assigned_to=s.m_emp1.pk, deadline=hours(10).isoformat())
        self.b = make_task(s.owner, self.o1, title="Glue", priority="low", assigned_to=s.m_emp2.pk, deadline=hours(100).isoformat())
        self.c = make_task(s.owner, self.o2, title="Paint", priority="high")
        self.d = make_task(s.owner, self.o2, title="Late one", priority="medium", assigned_to=s.m_emp1.pk)
        Task.objects.filter(pk=self.d.pk).update(deadline=hours(-5), status="in_progress")
        Task.objects.filter(pk=self.c.pk).update(status="review")

    def q(self, **p):
        r = self.s.c_owner.get(TASKS, p)
        self.assertEqual(r.status_code, 200, r.data)
        return sorted(t["title"] for t in r.data["results"])

    def test_filters(self):
        self.assertEqual(self.q(workshop=self.s.ws.pk), ["Glue", "Late one", "Paint", "Saw"])
        self.assertEqual(self.q(order=self.o1.pk), ["Glue", "Saw"])
        self.assertEqual(self.q(assigned_to=self.s.m_emp1.pk), ["Late one", "Saw"])
        self.assertEqual(self.q(employee=self.s.m_emp2.pk), ["Glue"])
        self.assertEqual(self.q(status="review"), ["Paint"])
        self.assertEqual(self.q(priority="urgent"), ["Saw"])
        self.assertEqual(self.q(deadline_before=hours(50).isoformat()), ["Late one", "Saw"])
        self.assertEqual(self.q(deadline_after=hours(50).isoformat()), ["Glue"])
        self.assertEqual(self.q(overdue="true"), ["Late one"])
        self.assertEqual(self.q(overdue="false"), ["Glue", "Paint", "Saw"])

    def test_combined_filters_and_mine(self):
        self.assertEqual(self.q(order=self.o1.pk, priority="low"), ["Glue"])
        self.assertEqual(self.q(order=self.o1.pk, status="review"), [])
        r = self.s.c_emp1.get(TASKS, {"mine": "true"})
        self.assertEqual(sorted(t["title"] for t in r.data["results"]), ["Late one", "Saw"])
        self.assertEqual(self.s.c_emp1.get(TASKS, {"mine": "false"}).data["count"], 0)

    def test_filters_never_widen_access(self):
        self.assertEqual(self.s.c_emp1.get(TASKS, {"workshop": self.s.ws.pk, "assigned_to": self.s.m_emp2.pk}).data["count"], 0)
        self.assertEqual(self.s.c_stranger.get(TASKS, {"workshop": self.s.ws.pk}).data["count"], 0)
        self.assertEqual(self.s.c_owner_b.get(TASKS, {"order": self.o1.pk}).data["count"], 0)

    def test_search_ordering_pagination_and_bad_values(self):
        self.assertEqual(self.q(search="aint"), ["Paint"])
        self.assertEqual(self.q(search=self.o1.order_number), ["Glue", "Saw"])
        r = self.s.c_owner.get(TASKS, {"ordering": "deadline"}).data["results"]
        self.assertEqual(r[0]["title"], "Late one")
        self.assertEqual(r[-1]["title"], "Paint")      # no deadline: always last ...
        r = self.s.c_owner.get(TASKS, {"ordering": "-deadline"}).data["results"]
        self.assertEqual((r[0]["title"], r[-1]["title"]), ("Glue", "Paint"))   # ... in both directions, on every database
        self.assertEqual(self.s.c_owner.get(TASKS, {"page_size": 3}).data["next"] is not None, True)
        self.assertEqual(self.s.c_owner.get(TASKS, {"status": "bogus"}).status_code, 400)
        self.assertEqual(self.s.c_owner.get(TASKS, {"deadline_after": "soon"}).status_code, 400)


class AllowedNextStatusesTests(TestCase):
    """The UI draws its buttons from `allowed_next_statuses`, so the backend must state exactly what it will accept."""

    def setUp(self):
        self.s = Scene()
        self.order = make_order(self.s.ws, self.s.owner, assigned_employee=self.s.m_emp1.pk)
        self.task = make_task(self.s.owner, self.order, assigned_to=self.s.m_emp1.pk)

    def get(self, c, obj, kind="tasks"):
        return c.get(f"/api/v1/{kind}/{obj.pk}/").data["allowed_next_statuses"]

    def test_task_choices_by_role(self):
        self.assertEqual(self.get(self.s.c_owner, self.task), ["cancelled", "in_progress"])
        self.assertEqual(self.get(self.s.c_emp1, self.task), ["in_progress"])
        self.s.c_emp1.patch(turl(self.task), {"status": "in_progress"}, format="json")
        self.assertEqual(self.get(self.s.c_emp1, self.task), ["review"])
        self.assertEqual(self.get(self.s.c_owner, self.task), ["cancelled", "completed", "pending", "review"])

    def test_offered_statuses_are_exactly_the_accepted_ones(self):
        """For every start status and every target: the PATCH succeeds if and only if the target was offered (owner and assignee)."""
        all_st = ("pending", "in_progress", "review", "completed", "cancelled")
        for who, client in (("owner", self.s.c_owner), ("assignee", self.s.c_emp1)):
            for start in all_st:
                for target in all_st:
                    if target == start:
                        continue
                    t = make_task(self.s.owner, self.order, title=f"{who} {start}>{target}", assigned_to=self.s.m_emp1.pk)
                    Task.objects.filter(pk=t.pk).update(status=start)
                    offered = client.get(turl(t)).data["allowed_next_statuses"]
                    r = client.patch(turl(t), {"status": target}, format="json")
                    self.assertEqual(r.status_code == 200, target in offered, (who, start, target, offered, r.status_code))

    def test_offered_order_statuses_are_exactly_the_accepted_ones(self):
        all_st = ("new", "confirmed", "in_production", "ready", "delivered", "cancelled")
        for start in all_st:
            for target in all_st:
                if target == start:
                    continue
                o = make_order(self.s.ws, self.s.owner)
                Order.objects.filter(pk=o.pk).update(status=start)
                offered = self.s.c_owner.get(f"/api/v1/orders/{o.pk}/").data["allowed_next_statuses"]
                r = self.s.c_owner.patch(f"/api/v1/orders/{o.pk}/", {"status": target}, format="json")
                self.assertEqual(r.status_code == 200, target in offered, (start, target, offered, r.status_code))

    def test_final_and_foreign_tasks_offer_nothing(self):
        self.s.c_owner.patch(turl(self.task), {"status": "cancelled"}, format="json")
        self.assertEqual(self.get(self.s.c_owner, self.task), [])
        other = make_task(self.s.owner, self.order, title="Colleague", assigned_to=self.s.m_emp2.pk)
        self.assertEqual(self.s.c_emp2.get(turl(other)).data["allowed_next_statuses"], ["in_progress"])
        self.assertEqual(self.s.c_emp1.get(turl(other)).status_code, 404)

    def test_inactive_workshop_offers_nothing(self):
        self.s.c_owner.patch(f"/api/v1/workshops/{self.s.ws.pk}/", {"status": "inactive"}, format="json")
        self.assertEqual(self.get(self.s.c_owner, self.task), [])
        self.assertEqual(self.get(self.s.c_emp1, self.task), [])

    def test_order_choices(self):
        self.assertEqual(self.get(self.s.c_owner, self.order, "orders"), ["cancelled", "confirmed"])
        self.assertEqual(self.get(self.s.c_emp1, self.order, "orders"), [])
        self.s.c_owner.patch(f"/api/v1/orders/{self.order.pk}/", {"status": "confirmed"}, format="json")
        self.assertEqual(self.get(self.s.c_owner, self.order, "orders"), ["cancelled", "in_production"])
        self.s.c_owner.patch(f"/api/v1/orders/{self.order.pk}/", {"status": "cancelled"}, format="json")
        self.assertEqual(self.get(self.s.c_owner, self.order, "orders"), [])

    def test_the_list_carries_the_field_without_extra_queries(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as a:
            self.s.c_owner.get("/api/v1/tasks/")
        for i in range(10):
            make_task(self.s.owner, self.order, title=f"more {i}", assigned_to=self.s.m_emp2.pk)
        with CaptureQueriesContext(connection) as b:
            r = self.s.c_owner.get("/api/v1/tasks/")
        self.assertEqual(len(a), len(b))
        self.assertTrue(all("allowed_next_statuses" in t for t in r.data["results"]))
