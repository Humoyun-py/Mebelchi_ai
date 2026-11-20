import shutil
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from apps.core.tests.helpers import client_for, make_user

TMP = tempfile.mkdtemp()


def png(name="room.png", size=(40, 30)):
    b = BytesIO()
    Image.new("RGB", size, "blue").save(b, "PNG")
    return SimpleUploadedFile(name, b.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=TMP)
class GalleryTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        self.a, self.b = make_user("a@x.com"), make_user("b@x.com")
        self.ca, self.cb = client_for(self.a), client_for(self.b)

    def test_upload_list_rename_favorite_delete(self):
        r = self.ca.post("/api/v1/gallery/", {"image": png(), "source": "room"}, format="multipart")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["width"], r.data["height"], r.data["name"]), (40, 30, "room"))
        gid = r.data["id"]
        self.assertEqual(self.ca.patch(f"/api/v1/gallery/{gid}/", {"name": "Living"}, format="json").data["name"], "Living")
        self.assertTrue(self.ca.post(f"/api/v1/gallery/{gid}/favorite/").data["favorite"])
        self.assertEqual(self.ca.get("/api/v1/gallery/?favorite=true&search=liv").data["count"], 1)
        self.assertEqual(self.ca.delete(f"/api/v1/gallery/{gid}/").status_code, 204)
        self.assertEqual(self.ca.get("/api/v1/gallery/").data["count"], 0)

    def test_rejects_fake_and_bad_files(self):
        fake = SimpleUploadedFile("evil.png", b"<?php echo 1; ?>", content_type="image/png")
        self.assertEqual(self.ca.post("/api/v1/gallery/", {"image": fake}, format="multipart").status_code, 400)
        exe = SimpleUploadedFile("a.exe", b"MZ", content_type="application/octet-stream")
        self.assertEqual(self.ca.post("/api/v1/gallery/", {"image": exe}, format="multipart").status_code, 400)

    def test_isolation_and_signed_urls(self):
        r = self.ca.post("/api/v1/gallery/", {"image": png()}, format="multipart")
        gid, url = r.data["id"], r.data["url"]
        self.assertEqual(self.cb.get(f"/api/v1/gallery/{gid}/").status_code, 404)
        self.assertEqual(self.cb.patch(f"/api/v1/gallery/{gid}/", {"name": "x"}, format="json").status_code, 404)
        self.assertEqual(self.cb.delete(f"/api/v1/gallery/{gid}/").status_code, 404)
        anon = APIClient()
        self.assertEqual(anon.get(url).status_code, 200)                                   # valid signature works without a header
        self.assertEqual(anon.get(f"/api/v1/gallery/{gid}/file/").status_code, 404)        # no signature
        self.assertEqual(anon.get(f"/api/v1/gallery/{gid}/file/?sig=forged").status_code, 404)
        other_sig = url.split("sig=")[1]
        g2 = self.cb.post("/api/v1/gallery/", {"image": png()}, format="multipart").data["id"]
        self.assertEqual(anon.get(f"/api/v1/gallery/{g2}/file/?sig={other_sig}").status_code, 404)  # signature bound to the id

    def test_storage_summary_and_limit(self):
        self.ca.post("/api/v1/gallery/", {"image": png()}, format="multipart")
        st = self.ca.get("/api/v1/users/me/storage/").data
        self.assertEqual(st["images"], 1)
        self.assertGreater(st["used_bytes"], 0)
        from apps.subscriptions.models import Plan, Subscription
        Plan.objects.filter(slug="free").update(storage_mb=0)
        Subscription.objects.filter(user=self.a).count()
        ca = client_for(type(self.a).objects.get(pk=self.a.pk))
        self.assertEqual(ca.post("/api/v1/gallery/", {"image": png()}, format="multipart").status_code, 403)

    def test_files_upload_validation(self):
        pdf = SimpleUploadedFile("plan.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        r = self.ca.post("/api/v1/files/", {"file": pdf}, format="multipart")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["kind"], "pdf")
        bad = SimpleUploadedFile("plan.pdf", b"not a pdf", content_type="application/pdf")
        self.assertEqual(self.ca.post("/api/v1/files/", {"file": bad}, format="multipart").status_code, 400)
        self.assertEqual(self.cb.get(f"/api/v1/files/{r.data['id']}/").status_code, 404)
        self.assertEqual(APIClient().get(r.data["url"]).status_code, 200)
        self.assertEqual(APIClient().get(f"/api/v1/files/{r.data['id']}/download/").status_code, 404)
