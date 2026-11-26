from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.core.tests.helpers import client_for, make_user
from apps.projects.models import Project
from apps.workspaces.models import Folder

URL = "/api/v1/folders/"


class FolderTests(TestCase):
    def setUp(self):
        self.a, self.b = make_user("a@x.com"), make_user("b@x.com")
        self.ca, self.cb = client_for(self.a), client_for(self.b)

    def test_anonymous_users_are_refused(self):
        from rest_framework.test import APIClient
        self.assertEqual(APIClient().get(URL).status_code, 401)
        self.assertEqual(APIClient().get("/api/v1/workspace/summary/").status_code, 401)

    def test_folders_are_private_to_their_owner(self):
        fid = self.ca.post(URL, {"name": "Kitchens"}, format="json").data["id"]
        self.assertEqual(len(self.cb.get(URL).data), 0)
        for call in (self.cb.get(f"{URL}{fid}/"), self.cb.patch(f"{URL}{fid}/", {"name": "x"}, format="json"), self.cb.delete(f"{URL}{fid}/")):
            self.assertEqual(call.status_code, 404)
        self.assertEqual(Folder.objects.get(pk=fid).name, "Kitchens")

    def test_the_owner_is_always_the_caller(self):
        fid = self.ca.post(URL, {"name": "Mine", "owner": self.b.pk}, format="json").data["id"]
        self.assertEqual(Folder.objects.get(pk=fid).owner, self.a)

    def test_a_parent_must_be_your_own_folder(self):
        theirs = Folder.objects.create(owner=self.b, name="B root")
        r = self.ca.post(URL, {"name": "Child", "parent": theirs.pk}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Folder.objects.filter(owner=self.a).count(), 0)
        mine = self.ca.post(URL, {"name": "Root"}, format="json").data["id"]
        self.assertEqual(self.ca.post(URL, {"name": "Child", "parent": mine}, format="json").status_code, 201)

    def test_names_are_unique_inside_one_parent_at_the_database_level(self):
        root = Folder.objects.create(owner=self.a, name="Root")
        Folder.objects.create(owner=self.a, name="Same", parent=root)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Folder.objects.create(owner=self.a, name="Same", parent=root)
        Folder.objects.create(owner=self.b, name="Same", parent=Folder.objects.create(owner=self.b, name="Root"))   # another owner: fine

    def test_duplicate_name_through_the_api_is_a_client_error(self):
        root = self.ca.post(URL, {"name": "Root"}, format="json").data["id"]
        self.assertEqual(self.ca.post(URL, {"name": "Dup", "parent": root}, format="json").status_code, 201)
        self.assertLess(self.ca.post(URL, {"name": "Dup", "parent": root}, format="json").status_code, 500)

    def test_invalid_input(self):
        self.assertEqual(self.ca.post(URL, {"name": ""}, format="json").status_code, 400)
        self.assertEqual(self.ca.post(URL, {"name": "x" * 121}, format="json").status_code, 400)
        self.assertEqual(self.ca.post(URL, {}, format="json").status_code, 400)

    def test_deleting_a_folder_removes_its_children_but_keeps_projects(self):
        root = Folder.objects.create(owner=self.a, name="Root")
        Folder.objects.create(owner=self.a, name="Child", parent=root)
        p = Project.objects.create(owner=self.a, name="Keep me", folder=root)
        self.assertEqual(self.ca.delete(f"{URL}{root.pk}/").status_code, 204)
        self.assertEqual(Folder.objects.count(), 0)
        self.assertTrue(Project.objects.filter(pk=p.pk).exists())

    def test_summary_counts_only_my_data(self):
        Folder.objects.create(owner=self.a, name="A1"); Folder.objects.create(owner=self.b, name="B1"); Folder.objects.create(owner=self.b, name="B2")
        Project.objects.create(owner=self.b, name="B project")
        s = self.ca.get("/api/v1/workspace/summary/").data
        self.assertEqual((s["folders"], s["projects"]), (1, 0))
