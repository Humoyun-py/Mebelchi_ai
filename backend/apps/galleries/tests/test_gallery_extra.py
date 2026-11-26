import shutil
import tempfile
from io import BytesIO
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from apps.core.signing import MAX_AGE
from apps.core.tests.helpers import client_for, make_user
from apps.galleries.models import GalleryImage
from apps.projects.models import Project

TMP = tempfile.mkdtemp()
URL = "/api/v1/gallery/"


def png(name="room.png"):
    b = BytesIO(); Image.new("RGB", (20, 10), "red").save(b, "PNG")
    return SimpleUploadedFile(name, b.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=TMP)
class GalleryExtraTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        self.a, self.b = make_user("a@x.com"), make_user("b@x.com")
        self.ca, self.cb = client_for(self.a), client_for(self.b)

    def test_creating_without_an_image_is_a_clean_400(self):
        r = self.ca.post(URL, {"name": "nothing"}, format="multipart")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(GalleryImage.objects.count(), 0)

    def test_anonymous_users_are_refused(self):
        self.assertEqual(APIClient().get(URL).status_code, 401)
        self.assertEqual(APIClient().post(URL, {"image": png()}, format="multipart").status_code, 401)

    def test_favorite_toggle_and_listing_are_scoped_to_the_owner(self):
        gid = self.ca.post(URL, {"image": png()}, format="multipart").data["id"]
        self.assertEqual(self.cb.post(f"{URL}{gid}/favorite/").status_code, 404)
        self.assertFalse(GalleryImage.objects.get(pk=gid).favorite)
        self.assertEqual(self.cb.get(URL).data["count"], 0)

    def test_an_image_cannot_be_attached_to_someone_elses_project(self):
        p = Project.objects.create(owner=self.b, name="B's")
        self.assertEqual(self.ca.post(URL, {"image": png(), "project": p.pk}, format="multipart").status_code, 400)
        self.assertEqual(GalleryImage.objects.count(), 0)

    def test_forged_owner_and_size_are_ignored(self):
        gid = self.ca.post(URL, {"image": png(), "owner": self.b.pk, "size_bytes": 1, "width": 9999}, format="multipart").data["id"]
        g = GalleryImage.objects.get(pk=gid)
        self.assertEqual((g.owner, g.width, g.height), (self.a, 20, 10))
        self.assertGreater(g.size_bytes, 1)

    def test_signed_link_expires_and_a_file_kind_signature_is_not_accepted(self):
        from apps.core.signing import sign_file
        r = self.ca.post(URL, {"image": png()}, format="multipart").data
        with mock.patch("django.core.signing.time.time", return_value=__import__("time").time() + MAX_AGE + 60):
            self.assertEqual(APIClient().get(r["url"]).status_code, 404)
        self.assertEqual(APIClient().get(f"{URL}{r['id']}/file/?sig={sign_file('file', r['id'])}").status_code, 404)
        self.assertEqual(APIClient().get(r["url"] + "&download=1").status_code, 200)
