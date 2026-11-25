import shutil
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from PIL import Image

from apps.core.tests.helpers import client_for, make_user
from apps.notifications.models import Notification
from apps.workshops.models import Workshop, WorkshopMember

from .helpers import API, WS, Scene, add_member, make_order, make_task, make_workshop, member_of

M = WorkshopMember


class WorkshopCreationTests(TestCase):
    def test_a_maker_creates_a_workshop_and_becomes_its_owner(self):
        u = make_user("m@x.com", "maker")
        r = client_for(u).post(WS, {"name": "Samarkand Furniture", "phone": "+998901112233", "address": "Samarkand"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["slug"], r.data["status"], r.data["my_role"]), ("samarkand-furniture", "active", "owner"))
        ws = Workshop.objects.get()
        self.assertEqual(ws.owner, u)
        m = M.objects.get(workshop=ws)
        self.assertEqual((m.user, m.role, m.status), (u, "owner", "active"))
        self.assertIsNotNone(m.joined_at)

    def test_slugs_stay_unique(self):
        u = make_user("m@x.com", "maker")
        a, b = make_workshop(u, "Same Name"), make_workshop(u, "Same Name")
        self.assertNotEqual(a.slug, b.slug)

    def test_only_makers_and_staff_can_create(self):
        home = make_user("home@x.com", "homeowner")
        r = client_for(home).post(WS, {"name": "Nope"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertIn("Furniture Maker", r.data["error"]["detail"])
        self.assertEqual(client_for(make_user("st@x.com", "homeowner", is_staff=True)).post(WS, {"name": "Staff WS"}, format="json").status_code, 201)
        self.assertEqual(client_for().post(WS, {"name": "Anon"}, format="json").status_code, 401)

    def test_validation(self):
        c = client_for(make_user("m@x.com", "maker"))
        self.assertEqual(c.post(WS, {"name": ""}, format="json").status_code, 400)
        self.assertEqual(c.post(WS, {"name": "a"}, format="json").status_code, 400)
        self.assertEqual(c.post(WS, {"name": "Ok", "email": "not-an-email"}, format="json").status_code, 400)
        self.assertEqual(c.post(WS, {"name": "Ok", "status": "suspended"}, format="json").status_code, 400)

    def test_owner_and_slug_cannot_be_forged_on_creation(self):
        me, other = make_user("m@x.com", "maker"), make_user("o@x.com", "maker")
        r = client_for(me).post(WS, {"name": "Mine", "owner": other.pk, "slug": "hijack"}, format="json")
        ws = Workshop.objects.get(pk=r.data["id"])
        self.assertEqual((ws.owner, ws.slug), (me, "mine"))


class VisibilityAndMultipleMembershipTests(TestCase):
    def setUp(self):
        self.s = Scene()

    def test_users_only_see_their_workshops(self):
        self.assertEqual({w["name"] for w in self.s.c_owner.get(WS).data["results"]}, {"Alpha Workshop"})
        self.assertEqual({w["name"] for w in self.s.c_emp1.get(WS).data["results"]}, {"Alpha Workshop"})
        self.assertEqual(self.s.c_stranger.get(WS).data["count"], 0)
        self.assertEqual(self.s.c_stranger.get(f"{WS}{self.s.ws.pk}/").status_code, 404)
        self.assertEqual(self.s.c_owner_b.get(f"{WS}{self.s.ws.pk}/").status_code, 404)

    def test_one_user_in_many_workshops_with_different_roles(self):
        add_member(self.s.wsb, self.s.emp1)  # emp1 is an employee of A and of B ...
        make_workshop(self.s.emp1, "Gamma Own")  # ... and owns a third one
        res = {w["name"]: w["my_role"] for w in self.s.c_emp1.get(WS).data["results"]}
        self.assertEqual(res, {"Alpha Workshop": "employee", "Beta Workshop": "employee", "Gamma Own": "owner"})

    def test_invited_and_removed_members_see_nothing(self):
        inv = make_user("inv@x.com", "maker")
        add_member(self.s.ws, inv, status="invited")
        gone = make_user("gone@x.com", "maker")
        add_member(self.s.ws, gone, status="removed")
        for u in (inv, gone):
            c = client_for(u)
            self.assertEqual(c.get(WS).data["count"], 0)
            self.assertEqual(c.get(f"{WS}{self.s.ws.pk}/").status_code, 404)
            self.assertEqual(c.get(f"{WS}{self.s.ws.pk}/members/").status_code, 404)

    def test_employee_cannot_change_the_workshop(self):
        self.assertEqual(self.s.c_emp1.patch(f"{WS}{self.s.ws.pk}/", {"name": "Hacked"}, format="json").status_code, 403)
        self.assertEqual(self.s.c_emp1.delete(f"{WS}{self.s.ws.pk}/").status_code, 403)
        self.assertEqual(self.s.c_stranger.patch(f"{WS}{self.s.ws.pk}/", {"name": "Hacked"}, format="json").status_code, 404)
        self.s.ws.refresh_from_db()
        self.assertEqual(self.s.ws.name, "Alpha Workshop")

    def test_owner_updates_workshop_but_not_slug_or_owner(self):
        r = self.s.c_owner.patch(f"{WS}{self.s.ws.pk}/", {"name": "Alpha Pro", "description": "d", "slug": "x", "owner": self.s.emp1.pk}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.s.ws.refresh_from_db()
        self.assertEqual((self.s.ws.name, self.s.ws.slug, self.s.ws.owner), ("Alpha Pro", "alpha-workshop", self.s.owner))


class WorkshopStatusTests(TestCase):
    def setUp(self):
        self.s = Scene()

    def test_owner_can_deactivate_but_not_suspend(self):
        self.assertEqual(self.s.c_owner.patch(f"{WS}{self.s.ws.pk}/", {"status": "inactive"}, format="json").status_code, 200)
        self.assertEqual(self.s.c_owner.patch(f"{WS}{self.s.ws.pk}/", {"status": "suspended"}, format="json").status_code, 400)

    def test_inactive_workshop_is_read_only_for_business_data(self):
        order = make_order(self.s.ws, self.s.owner)
        self.s.c_owner.patch(f"{WS}{self.s.ws.pk}/", {"status": "inactive"}, format="json")
        r = self.s.c_owner.post(API + "orders/", {"workshop": self.s.ws.pk, "title": "x", "customer_name": "y"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.s.c_owner.patch(f"{API}orders/{order.pk}/", {"title": "z"}, format="json").status_code, 403)
        self.assertEqual(self.s.c_owner.post(f"{WS}{self.s.ws.pk}/members/", {"email": self.s.stranger.email}, format="json").status_code, 403)
        self.assertEqual(self.s.c_owner.get(f"{API}orders/{order.pk}/").status_code, 200)   # reading still works
        self.assertEqual(self.s.c_owner.patch(f"{WS}{self.s.ws.pk}/", {"status": "active"}, format="json").status_code, 200)  # and it can be reopened
        self.assertEqual(self.s.c_owner.patch(f"{API}orders/{order.pk}/", {"title": "z"}, format="json").status_code, 200)

    def test_suspended_workshop_is_frozen_even_for_its_owner(self):
        Workshop.objects.filter(pk=self.s.ws.pk).update(status="suspended")
        self.assertEqual(self.s.c_owner.patch(f"{WS}{self.s.ws.pk}/", {"status": "active"}, format="json").status_code, 403)
        self.assertEqual(self.s.c_owner.post(API + "orders/", {"workshop": self.s.ws.pk, "title": "x", "customer_name": "y"}, format="json").status_code, 403)
        self.assertEqual(self.s.c_owner.get(f"{WS}{self.s.ws.pk}/").status_code, 200)

    def test_delete_rules(self):
        empty = make_workshop(self.s.owner, "Empty One")
        self.assertEqual(self.s.c_owner.delete(f"{WS}{empty.pk}/").status_code, 204)
        self.assertFalse(Workshop.objects.filter(pk=empty.pk).exists())
        make_order(self.s.ws, self.s.owner)
        r = self.s.c_owner.delete(f"{WS}{self.s.ws.pk}/")
        self.assertEqual(r.status_code, 409)
        self.assertIn("inactive", r.data["error"]["detail"])
        self.assertTrue(Workshop.objects.filter(pk=self.s.ws.pk).exists())


class MemberInvitationTests(TestCase):
    def setUp(self):
        self.s = Scene()
        self.url = f"{WS}{self.s.ws.pk}/members/"

    def test_full_invitation_flow(self):
        r = self.s.c_owner.post(self.url, {"email": "STRANGER@x.com"}, format="json")  # case-insensitive
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["role"], r.data["status"]), ("employee", "invited"))
        self.assertTrue(Notification.objects.filter(user=self.s.stranger, title__startswith="Invitation").exists())
        inv = self.s.c_stranger.get(API + "workshop-invitations/").data["results"]
        self.assertEqual([(i["workshop"]["name"], i["invited_by"]["full_name"]) for i in inv], [("Alpha Workshop", "Test User")])
        mid = r.data["id"]
        self.assertEqual(self.s.c_stranger.get(WS).data["count"], 0)  # not a member yet
        a = self.s.c_stranger.patch(f"{self.url}{mid}/", {"status": "active"}, format="json")
        self.assertEqual((a.status_code, a.data["status"]), (200, "active"), a.data)
        self.assertIsNotNone(M.objects.get(pk=mid).joined_at)
        self.assertEqual(self.s.c_stranger.get(WS).data["count"], 1)
        self.assertEqual(self.s.c_stranger.get(API + "workshop-invitations/").data["count"], 0)

    def test_invitee_can_decline(self):
        mid = self.s.c_owner.post(self.url, {"email": self.s.stranger.email}, format="json").data["id"]
        self.assertEqual(self.s.c_stranger.patch(f"{self.url}{mid}/", {"status": "removed"}, format="json").status_code, 200)
        self.assertEqual(M.objects.get(pk=mid).status, "removed")

    def test_cannot_invite_twice_or_invite_members(self):
        self.s.c_owner.post(self.url, {"email": self.s.stranger.email}, format="json")
        again = self.s.c_owner.post(self.url, {"email": self.s.stranger.email}, format="json")
        self.assertEqual(again.status_code, 400)
        self.assertIn("already been invited", str(again.data))
        self.assertEqual(self.s.c_owner.post(self.url, {"email": self.s.emp1.email}, format="json").status_code, 400)
        self.assertEqual(self.s.c_owner.post(self.url, {"email": self.s.owner.email}, format="json").status_code, 400)
        self.assertEqual(M.objects.filter(workshop=self.s.ws, user=self.s.stranger).count(), 1)

    def test_unknown_email_and_bad_input(self):
        self.assertEqual(self.s.c_owner.post(self.url, {"email": "nobody@x.com"}, format="json").status_code, 400)
        self.assertEqual(self.s.c_owner.post(self.url, {"email": "bad"}, format="json").status_code, 400)
        self.assertEqual(self.s.c_owner.post(self.url, {}, format="json").status_code, 400)
        inactive = make_user("off@x.com", "maker")
        inactive.is_active = False
        inactive.save()
        self.assertEqual(self.s.c_owner.post(self.url, {"email": "off@x.com"}, format="json").status_code, 400)

    def test_employees_and_strangers_cannot_invite(self):
        self.assertEqual(self.s.c_emp1.post(self.url, {"email": self.s.stranger.email}, format="json").status_code, 403)
        self.assertEqual(self.s.c_stranger.post(self.url, {"email": self.s.stranger.email}, format="json").status_code, 404)
        self.assertEqual(self.s.c_owner_b.post(self.url, {"email": self.s.stranger.email}, format="json").status_code, 404)

    def test_nobody_else_can_answer_my_invitation(self):
        mid = self.s.c_owner.post(self.url, {"email": self.s.stranger.email}, format="json").data["id"]
        self.assertEqual(self.s.c_owner.patch(f"{self.url}{mid}/", {"status": "active"}, format="json").status_code, 403)
        self.assertEqual(self.s.c_emp1.patch(f"{self.url}{mid}/", {"status": "active"}, format="json").status_code, 404)
        self.assertEqual(M.objects.get(pk=mid).status, "invited")

    def test_cannot_accept_an_invitation_twice_or_after_removal(self):
        mid = self.s.c_owner.post(self.url, {"email": self.s.stranger.email}, format="json").data["id"]
        self.s.c_stranger.patch(f"{self.url}{mid}/", {"status": "active"}, format="json")
        self.assertEqual(self.s.c_stranger.patch(f"{self.url}{mid}/", {"status": "active"}, format="json").status_code, 403)


class MemberRemovalTests(TestCase):
    def setUp(self):
        self.s = Scene()
        self.url = f"{WS}{self.s.ws.pk}/members/"

    def test_removal_is_soft_and_keeps_history(self):
        order = make_order(self.s.ws, self.s.owner, assigned_employee=self.s.m_emp1.pk)
        task = make_task(self.s.owner, order, assigned_to=self.s.m_emp1.pk)
        self.assertEqual(self.s.c_owner.delete(f"{self.url}{self.s.m_emp1.pk}/").status_code, 204)
        m = M.objects.get(pk=self.s.m_emp1.pk)
        self.assertEqual(m.status, "removed")
        self.assertIsNotNone(m.removed_at)
        order.refresh_from_db()
        task.refresh_from_db()
        self.assertEqual((order.assigned_employee_id, task.assigned_to_id), (m.pk, m.pk))  # records still point at the (former) member
        self.assertEqual(self.s.c_emp1.get(WS).data["count"], 0)
        self.assertEqual(self.s.c_emp1.get(f"{API}tasks/{task.pk}/").status_code, 404)
        self.assertEqual(self.s.c_emp1.get(f"{API}orders/{order.pk}/").status_code, 404)

    def test_removed_members_are_still_shown_to_the_owner_with_their_status(self):
        self.s.c_owner.delete(f"{self.url}{self.s.m_emp1.pk}/")
        rows = {m["user"]["id"]: m["status"] for m in self.s.c_owner.get(self.url).data["results"]}
        self.assertEqual(rows[self.s.emp1.pk], "removed")
        removed = self.s.c_owner.get(self.url, {"status": "removed"}).data["results"]
        self.assertEqual(len(removed), 1)

    def test_removed_member_can_be_invited_again_without_a_duplicate_row(self):
        self.s.c_owner.delete(f"{self.url}{self.s.m_emp1.pk}/")
        r = self.s.c_owner.post(self.url, {"email": self.s.emp1.email}, format="json")
        self.assertEqual((r.status_code, r.data["status"], r.data["id"]), (201, "invited", self.s.m_emp1.pk))
        self.assertEqual(M.objects.filter(workshop=self.s.ws, user=self.s.emp1).count(), 1)

    def test_owner_cannot_be_removed(self):
        owner_row = member_of(self.s.ws, self.s.owner)
        r = self.s.c_owner.delete(f"{self.url}{owner_row.pk}/")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(M.objects.get(pk=owner_row.pk).status, "active")
        self.assertEqual(self.s.c_owner.patch(f"{self.url}{owner_row.pk}/", {"status": "removed"}, format="json").status_code, 400)

    def test_only_the_owner_removes_others(self):
        self.assertEqual(self.s.c_emp1.delete(f"{self.url}{self.s.m_emp2.pk}/").status_code, 404)   # not even visible to emp1
        self.assertEqual(self.s.c_emp1.delete(f"{self.url}{self.s.m_emp1.pk}/").status_code, 403)   # own row, but not allowed to delete
        self.assertEqual(self.s.c_stranger.delete(f"{self.url}{self.s.m_emp1.pk}/").status_code, 404)
        self.assertEqual(self.s.c_owner_b.delete(f"{self.url}{self.s.m_emp1.pk}/").status_code, 404)
        self.assertEqual(M.objects.filter(workshop=self.s.ws, status="active").count(), 3)

    def test_employee_can_leave(self):
        r = self.s.c_emp1.patch(f"{self.url}{self.s.m_emp1.pk}/", {"status": "removed"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(M.objects.get(pk=self.s.m_emp1.pk).status, "removed")

    def test_employee_cannot_change_colleagues(self):
        self.assertEqual(self.s.c_emp1.patch(f"{self.url}{self.s.m_emp2.pk}/", {"status": "removed"}, format="json").status_code, 404)
        self.assertEqual(self.s.c_emp1.patch(f"{self.url}{self.s.m_emp1.pk}/", {"role": "owner", "confirm_transfer": True}, format="json").status_code, 403)
        self.assertEqual(M.objects.filter(workshop=self.s.ws, role="owner").count(), 1)


class OwnershipTests(TestCase):
    def setUp(self):
        self.s = Scene()
        self.url = f"{WS}{self.s.ws.pk}/members/"

    def test_transfer_needs_explicit_confirmation(self):
        r = self.s.c_owner.patch(f"{self.url}{self.s.m_emp1.pk}/", {"role": "owner"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("confirm_transfer", r.data["error"]["fields"])
        self.assertEqual(member_of(self.s.ws, self.s.owner).role, "owner")

    def test_confirmed_transfer_swaps_roles_and_keeps_exactly_one_owner(self):
        r = self.s.c_owner.patch(f"{self.url}{self.s.m_emp1.pk}/", {"role": "owner", "confirm_transfer": True}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((member_of(self.s.ws, self.s.emp1).role, member_of(self.s.ws, self.s.owner).role), ("owner", "employee"))
        self.assertEqual(M.objects.filter(workshop=self.s.ws, role="owner").count(), 1)
        self.s.ws.refresh_from_db()
        self.assertEqual(self.s.ws.owner, self.s.emp1)
        # the former owner has lost owner powers immediately
        self.assertEqual(self.s.c_owner.patch(f"{WS}{self.s.ws.pk}/", {"name": "Mine still?"}, format="json").status_code, 403)
        self.assertEqual(self.s.c_emp1.patch(f"{WS}{self.s.ws.pk}/", {"name": "New boss"}, format="json").status_code, 200)

    def test_cannot_transfer_to_non_members_or_inactive_members(self):
        invited = add_member(self.s.ws, make_user("inv@x.com", "maker"), status="invited")
        removed = add_member(self.s.ws, make_user("rem@x.com", "maker"), status="removed")
        for m in (invited, removed):
            self.assertEqual(self.s.c_owner.patch(f"{self.url}{m.pk}/", {"role": "owner", "confirm_transfer": True}, format="json").status_code, 400)
        self.assertEqual(M.objects.filter(workshop=self.s.ws, role="owner").count(), 1)

    def test_owner_cannot_demote_themselves_directly(self):
        own = member_of(self.s.ws, self.s.owner)
        r = self.s.c_owner.patch(f"{self.url}{own.pk}/", {"role": "employee"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(member_of(self.s.ws, self.s.owner).role, "owner")

    def test_database_enforces_the_invariants(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            M.objects.create(workshop=self.s.ws, user=self.s.stranger, role="owner", status="active")      # second owner
        with self.assertRaises(IntegrityError), transaction.atomic():
            M.objects.create(workshop=self.s.wsb, user=self.s.stranger, role="owner", status="invited")     # an owner must be active
        with self.assertRaises(IntegrityError), transaction.atomic():
            M.objects.create(workshop=self.s.ws, user=self.s.emp1, role="employee", status="active")        # duplicate membership


class RosterPrivacyTests(TestCase):
    def test_employees_see_names_but_not_emails_or_inactive_rows(self):
        s = Scene()
        add_member(s.ws, make_user("gone@x.com", "maker"), status="removed")
        add_member(s.ws, make_user("inv@x.com", "maker"), status="invited")
        rows = s.c_emp1.get(f"{WS}{s.ws.pk}/members/").data["results"]
        self.assertEqual(len(rows), 3)  # owner + 2 employees, all active
        for r in rows:
            if r["user"]["id"] != s.emp1.pk:
                self.assertNotIn("email", r["user"])
        mine = next(r for r in rows if r["user"]["id"] == s.emp1.pk)
        self.assertEqual(mine["user"]["email"], "emp1@a.com")
        owner_rows = s.c_owner.get(f"{WS}{s.ws.pk}/members/").data["results"]
        self.assertEqual(len(owner_rows), 5)
        self.assertTrue(all("email" in r["user"] for r in owner_rows))


TMP = tempfile.mkdtemp()


def png(name="logo.png"):
    b = BytesIO()
    Image.new("RGB", (30, 20), "navy").save(b, "PNG")
    return SimpleUploadedFile(name, b.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=TMP)
class LogoTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def test_logo_upload_signed_link_and_removal(self):
        s = Scene()
        url = f"{WS}{s.ws.pk}/logo/"
        r = s.c_owner.post(url, {"logo": png()}, format="multipart")
        self.assertEqual(r.status_code, 200, r.data)
        link = r.data["logo_url"]
        self.assertIn("/logo-file/?sig=", link)
        self.assertEqual(client_for().get(link).status_code, 200)               # the signed link works without credentials
        self.assertEqual(client_for().get(link.split("?")[0]).status_code, 404)  # unsigned does not
        self.assertEqual(client_for().get(f"{WS}{s.wsb.pk}/logo-file/?sig=" + link.split("sig=")[1]).status_code, 404)  # bound to one workshop
        self.assertEqual(s.c_owner.delete(url).data["logo_url"], None)

    def test_logo_rules(self):
        s = Scene()
        url = f"{WS}{s.ws.pk}/logo/"
        fake = SimpleUploadedFile("x.png", b"not an image", content_type="image/png")
        self.assertEqual(s.c_owner.post(url, {"logo": fake}, format="multipart").status_code, 400)
        self.assertEqual(s.c_emp1.post(url, {"logo": png()}, format="multipart").status_code, 403)
        self.assertEqual(s.c_stranger.post(url, {"logo": png()}, format="multipart").status_code, 404)
