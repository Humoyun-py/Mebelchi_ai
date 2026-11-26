import os
import shutil
import tempfile
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.core.signing import MAX_AGE, sign_file
from apps.core.tests.helpers import client_for, make_user
from apps.files.models import UserFile
from apps.projects.models import Project

TMP = tempfile.mkdtemp()
URL = "/api/v1/files/"


def pdf(name="plan.pdf", body=b"%PDF-1.4 test"):
    return SimpleUploadedFile(name, body, content_type="application/pdf")


@override_settings(MEDIA_ROOT=TMP)
class UserFileTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        self.a, self.b = make_user("a@x.com"), make_user("b@x.com")
        self.ca, self.cb = client_for(self.a), client_for(self.b)

    def upload(self, client=None, **kw):
        r = (client or self.ca).post(URL, {"file": kw.pop("file", None) or pdf(), **kw}, format="multipart")
        self.assertEqual(r.status_code, 201, r.data)
        return r.data

    # --- tenant isolation
    def test_every_route_is_closed_to_anonymous_users(self):
        f = self.upload()
        anon = APIClient()
        for call in (anon.get(URL), anon.get(f"{URL}{f['id']}/"), anon.post(URL, {"file": pdf()}, format="multipart"), anon.delete(f"{URL}{f['id']}/")):
            self.assertEqual(call.status_code, 401)

    def test_another_user_can_neither_see_change_nor_delete_a_file(self):
        f = self.upload()
        self.assertEqual(self.cb.get(URL).data["count"], 0)
        self.assertEqual(self.cb.get(f"{URL}{f['id']}/").status_code, 404)
        self.assertEqual(self.cb.patch(f"{URL}{f['id']}/", {"name": "x"}, format="json").status_code, 404)
        self.assertEqual(self.cb.delete(f"{URL}{f['id']}/").status_code, 404)
        self.assertEqual(UserFile.objects.get(pk=f["id"]).name, "plan.pdf")

    def test_a_file_cannot_be_attached_to_someone_elses_project(self):
        p = Project.objects.create(owner=self.b, name="B's project")
        r = self.ca.post(URL, {"file": pdf(), "project": p.pk}, format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(UserFile.objects.count(), 0)

    # --- invalid input and error handling
    def test_creating_without_a_file_is_a_clean_400_not_a_server_error(self):
        r = self.ca.post(URL, {"name": "nothing"}, format="multipart")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(UserFile.objects.count(), 0)

    def test_disallowed_and_oversized_files_are_refused(self):
        self.assertEqual(self.ca.post(URL, {"file": SimpleUploadedFile("run.exe", b"MZ")}, format="multipart").status_code, 400)
        self.assertEqual(self.ca.post(URL, {"file": SimpleUploadedFile("noext", b"data")}, format="multipart").status_code, 400)
        with override_settings(MAX_FILE_UPLOAD_BYTES=10):
            self.assertEqual(self.ca.post(URL, {"file": pdf(body=b"%PDF-1.4 " + b"x" * 50)}, format="multipart").status_code, 400)
        self.assertEqual(UserFile.objects.count(), 0)

    def test_server_stamped_fields_cannot_be_forged(self):
        f = self.upload(kind="model", size_bytes=1, owner=self.b.pk)
        row = UserFile.objects.get(pk=f["id"])
        self.assertEqual((row.owner, row.kind, row.size_bytes), (self.a, "pdf", len(b"%PDF-1.4 test")))
        self.ca.patch(f"{URL}{f['id']}/", {"kind": "model", "size_bytes": 99, "name": "renamed.pdf"}, format="json")
        row.refresh_from_db()
        self.assertEqual((row.kind, row.size_bytes, row.name), ("pdf", len(b"%PDF-1.4 test"), "renamed.pdf"))

    def test_filters_and_search(self):
        self.upload(file=pdf("kitchen.pdf")); self.upload(file=SimpleUploadedFile("sofa.glb", b"glTF"))
        self.assertEqual(self.ca.get(URL, {"kind": "model"}).data["count"], 1)
        self.assertEqual(self.ca.get(URL, {"search": "kitch"}).data["count"], 1)

    # --- storage
    def test_deleting_a_file_removes_the_bytes_from_disk(self):
        f = self.upload()
        path = UserFile.objects.get(pk=f["id"]).file.path
        self.assertTrue(os.path.exists(path))
        self.assertEqual(self.ca.delete(f"{URL}{f['id']}/").status_code, 204)
        self.assertFalse(os.path.exists(path))

    def test_the_stored_name_is_random_and_keeps_only_a_lowercase_extension(self):
        f = self.upload(file=pdf("../../etc/PASSWD.PDF"))
        name = UserFile.objects.get(pk=f["id"]).file.name
        self.assertRegex(name, rf"^files/{self.a.pk}/[0-9a-f]{{32}}\.pdf$")

    # --- signed download links
    def test_signed_link_downloads_without_a_header_and_is_bound_to_file_and_kind(self):
        f1, f2 = self.upload(), self.upload(file=pdf("two.pdf"))
        anon = APIClient()
        r = anon.get(f1["url"])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b"".join(r.streaming_content), b"%PDF-1.4 test")
        sig = f1["url"].split("sig=")[1]
        self.assertEqual(anon.get(f"{URL}{f2['id']}/download/?sig={sig}").status_code, 404)           # signed for another file
        self.assertEqual(anon.get(f"{URL}{f1['id']}/download/?sig={sign_file('image', f1['id'])}").status_code, 404)  # gallery-kind signature
        for bad in ("", "garbage", sig[:-3] + "xxx"):
            self.assertEqual(anon.get(f"{URL}{f1['id']}/download/?sig={bad}").status_code, 404)

    def test_signed_link_expires(self):
        f = self.upload()
        with mock.patch("django.core.signing.time.time", return_value=__import__("time").time() + MAX_AGE + 60):
            self.assertEqual(APIClient().get(f["url"]).status_code, 404)
        self.assertEqual(APIClient().get(f["url"]).status_code, 200)

    def test_a_valid_signature_for_a_deleted_file_is_404(self):
        f = self.upload()
        self.ca.delete(f"{URL}{f['id']}/")
        self.assertEqual(APIClient().get(f["url"]).status_code, 404)
