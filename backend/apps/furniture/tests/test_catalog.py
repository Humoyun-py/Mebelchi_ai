import json
import struct
import tempfile
import shutil
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.core.tests.helpers import client_for, make_user
from apps.furniture import glb
from apps.furniture.models import FurnitureImage, FurnitureTemplate as T
from apps.workshops.tests.helpers import make_workshop

URL = "/api/v1/furniture/templates/"
SIZE = {"width": 900, "height": 720, "depth": 500, "thickness": 18, "shelves": 1, "doors": 2, "drawers": 0}
TMP = tempfile.mkdtemp()


def png(name="a.png"):
    b = BytesIO()
    Image.new("RGB", (8, 8), "blue").save(b, "PNG")
    return SimpleUploadedFile(name, b.getvalue(), content_type="image/png")


def make_glb(doc=None, binary=b"\x00\x00\x00\x00"):
    doc = doc or {"asset": {"version": "2.0"}, "meshes": [{"primitives": []}], "nodes": [{"mesh": 0}], "buffers": [{"byteLength": 4}]}
    js = json.dumps(doc).encode()
    js += b" " * (-len(js) % 4)
    total = 12 + 8 + len(js) + 8 + len(binary)
    return (struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js
            + struct.pack("<II", len(binary), 0x004E4942) + binary)


@override_settings(MEDIA_ROOT=TMP)
class CatalogBase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        self.owner, self.other, self.home = make_user("o@x.com", "workshop"), make_user("p@x.com", "workshop"), make_user("h@x.com", "homeowner")
        self.admin = make_user("adm@x.com", "maker", is_staff=True)
        self.ws, self.ws2 = make_workshop(self.owner, "Alpha"), make_workshop(self.other, "Beta")
        self.co, self.cp, self.ch, self.ca = client_for(self.owner), client_for(self.other), client_for(self.home), client_for(self.admin)

    def add(self, c=None, **kw):
        body = {"workshop": self.ws.pk, "category": "kitchen", "name": "Test cabinet", "price": "120.50", **SIZE, **kw}
        return (c or self.co).post(URL, body, format="json")


class CrudTests(CatalogBase):
    def test_owner_adds_an_item_which_starts_pending_with_sizes_in_defaults(self):
        r = self.add()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["status"], r.data["workshop"], r.data["price"]), ("pending", self.ws.pk, "120.50"))
        self.assertEqual((r.data["defaults"]["width"], r.data["defaults"]["depth"]), (900, 500))
        self.assertTrue(r.data["slug"].startswith("alpha"))
        self.assertTrue(AuditLog.objects.filter(event="catalog.created").exists())

    def test_defaults_form_works_too(self):
        r = self.co.post(URL, {"workshop": self.ws.pk, "category": "office", "name": "D", "defaults": SIZE}, format="json")
        self.assertEqual(r.status_code, 201, r.data)

    def test_both_forms_at_once_is_refused(self):
        self.assertEqual(self.add(defaults=SIZE).status_code, 400)

    def test_invalid_sizes_category_color_price(self):
        self.assertEqual(self.add(width=50).status_code, 400)
        self.assertEqual(self.add(category="spaceship").status_code, 400)
        self.assertEqual(self.add(color="red").status_code, 400)
        self.assertEqual(self.add(price="-1").status_code, 400)
        r = self.co.post(URL, {"workshop": self.ws.pk, "category": "kitchen", "name": "x"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_duplicates_are_refused_but_a_different_size_is_fine(self):
        self.assertEqual(self.add().status_code, 201)
        self.assertEqual(self.add(name="  test   CABINET ").status_code, 400)
        self.assertEqual(self.add(width=1000).status_code, 201)
        self.assertEqual(self.add(c=self.cp, workshop=self.ws2.pk).status_code, 201)       # another workshop may sell the same thing

    def test_removed_item_frees_its_name(self):
        i = self.add().data["id"]
        self.assertEqual(self.co.delete(f"{URL}{i}/").status_code, 204)
        self.assertEqual(self.add().status_code, 201)

    def test_only_the_owner_of_an_active_workshop_may_add(self):
        self.assertEqual(self.add(c=self.ch).status_code, 403)
        self.assertEqual(self.add(c=self.cp).status_code, 403)                              # someone else's workshop
        self.assertEqual(client_for(self.owner).post(URL, {"category": "kitchen", "name": "n", **SIZE}, format="json").status_code, 400)   # no workshop
        self.assertEqual(APIClient().post(URL, {}, format="json").status_code, 401)
        pending = make_workshop(make_user("n@x.com", "workshop"), "New", approve=False)
        self.assertEqual(self.add(c=client_for(pending.owner), workshop=pending.pk).status_code, 403)

    def test_admin_adds_platform_items_that_are_approved_at_once(self):
        r = self.ca.post(URL, {"category": "living", "name": "Platform shelf", **SIZE}, format="json")
        self.assertEqual((r.status_code, r.data["status"], r.data["workshop"]), (201, "approved", None))

    def test_update_and_delete_are_owner_only(self):
        i = self.add().data["id"]
        self.assertEqual(self.cp.patch(f"{URL}{i}/", {"price": "1"}, format="json").status_code, 404)   # not visible to others while pending
        self.assertEqual(self.co.patch(f"{URL}{i}/", {"price": "99.00"}, format="json").data["price"], "99.00")
        self.ca.post(f"{URL}{i}/review/", {"status": "approved"}, format="json")
        self.assertEqual(self.cp.patch(f"{URL}{i}/", {"price": "1"}, format="json").status_code, 403)   # visible now, still not theirs
        self.assertEqual(self.cp.delete(f"{URL}{i}/").status_code, 403)
        self.assertEqual(self.ch.put(f"{URL}{i}/", {}, format="json").status_code, 403)

    def test_seeded_platform_items_cannot_be_changed_by_workshops(self):
        t = T.objects.filter(workshop__isnull=True).first()
        self.assertEqual(self.co.patch(f"{URL}{t.pk}/", {"price": "1"}, format="json").status_code, 403)
        self.assertEqual(self.co.delete(f"{URL}{t.pk}/").status_code, 403)

    def test_suspended_workshop_cannot_edit_its_items(self):
        i = self.add().data["id"]
        self.ws.status = "suspended"
        self.ws.save()
        self.assertEqual(self.co.patch(f"{URL}{i}/", {"price": "5"}, format="json").status_code, 403)


class VisibilityAndApprovalTests(CatalogBase):
    def test_pending_items_are_visible_only_to_their_workshop_and_admins(self):
        i = self.add().data["id"]
        ids = lambda c: {x["id"] for x in c.get(URL).data}
        self.assertIn(i, ids(self.co))
        self.assertIn(i, ids(self.ca))
        self.assertNotIn(i, ids(self.ch))
        self.assertNotIn(i, ids(self.cp))
        self.assertEqual(self.ch.get(f"{URL}{i}/").status_code, 404)

    def test_approval_makes_it_public_and_rejection_needs_a_reason(self):
        i = self.add().data["id"]
        self.assertEqual(self.co.post(f"{URL}{i}/review/", {"status": "approved"}, format="json").status_code, 403)
        self.assertEqual(self.ca.post(f"{URL}{i}/review/", {"status": "rejected"}, format="json").status_code, 400)
        r = self.ca.post(f"{URL}{i}/review/", {"status": "rejected", "note": "Photos missing"}, format="json")
        self.assertEqual((r.data["status"], r.data["review_note"]), ("rejected", "Photos missing"))
        r = self.ca.post(f"{URL}{i}/review/", {"status": "approved"}, format="json")
        self.assertEqual((r.data["status"], r.data["review_note"]), ("approved", ""))
        self.assertIn(i, {x["id"] for x in self.ch.get(URL).data})

    def test_changing_what_the_item_is_sends_it_back_to_review_but_price_does_not(self):
        i = self.add().data["id"]
        self.ca.post(f"{URL}{i}/review/", {"status": "approved"}, format="json")
        self.assertEqual(self.co.patch(f"{URL}{i}/", {"price": "10", "is_available": False}, format="json").data["status"], "approved")
        r = self.co.patch(f"{URL}{i}/", {"width": 1200}, format="json")
        self.assertEqual((r.status_code, r.data["status"], r.data["defaults"]["width"]), (200, "pending", 1200))
        self.assertEqual(r.data["defaults"]["height"], 720)                                 # other sizes kept

    def test_pending_items_are_not_offered_by_the_room_designer(self):
        from apps.rooms import services
        i = self.add(name="Secret").data["id"]
        slug = T.objects.get(pk=i).slug
        self.assertNotIn(slug, [t["slug"] for t in services.context().templates])
        self.ca.post(f"{URL}{i}/review/", {"status": "approved"}, format="json")
        self.assertIn(slug, [t["slug"] for t in services.context().templates])

    def test_filters_and_search(self):
        i = self.add(name="Corner unit", manufacturer="Acme").data["id"]
        self.ca.post(f"{URL}{i}/review/", {"status": "approved"}, format="json")
        self.assertEqual([x["id"] for x in self.ch.get(URL, {"search": "acme"}).data], [i])
        self.assertEqual([x["id"] for x in self.ch.get(URL, {"workshop": self.ws.pk}).data], [i])
        self.assertTrue(all(x["category"] == "kitchen" for x in self.ch.get(URL, {"category": "kitchen"}).data))


class ImageTests(CatalogBase):
    def setUp(self):
        super().setUp()
        self.i = self.add().data["id"]
        self.u = f"{URL}{self.i}/images/"

    def up(self, view="front", c=None, f=None):
        return (c or self.co).post(self.u, {"view": view, "image": f or png()}, format="multipart")

    def test_six_sides_one_image_each_and_replace(self):
        for v in ("front", "left", "right", "back", "top", "bottom"):
            self.assertEqual(self.up(v).status_code, 200, v)
        r = self.co.get(f"{URL}{self.i}/")
        self.assertEqual(sorted(x["view"] for x in r.data["images"]), sorted(["front", "left", "right", "back", "top", "bottom"]))
        self.up("front")
        self.assertEqual(FurnitureImage.objects.filter(template_id=self.i, view="front").count(), 1)

    def test_signed_url_serves_the_image_without_a_token(self):
        url = self.up().data["images"][0]["url"]
        self.assertEqual(APIClient().get(url).status_code, 200)
        self.assertEqual(APIClient().get(url.split("?")[0]).status_code, 404)
        self.assertEqual(APIClient().get(url + "x").status_code, 404)

    def test_bad_input(self):
        self.assertEqual(self.up("diagonal").status_code, 400)
        self.assertEqual(self.up(f=SimpleUploadedFile("a.png", b"not an image", content_type="image/png")).status_code, 400)
        self.assertEqual(self.co.post(self.u, {"view": "front"}, format="multipart").status_code, 400)

    def test_only_the_owner_may_change_images_and_delete_works(self):
        self.ca.post(f"{URL}{self.i}/review/", {"status": "approved"}, format="json")
        self.assertEqual(self.up(c=self.cp).status_code, 403)
        self.up()
        self.assertEqual(self.cp.delete(self.u + "?view=front").status_code, 403)
        self.assertEqual(self.co.delete(self.u + "?view=front").status_code, 200)
        self.assertEqual(self.co.delete(self.u + "?view=front").status_code, 400)


class ModelTests(CatalogBase):
    def setUp(self):
        super().setUp()
        self.i = self.add().data["id"]
        self.ca.post(f"{URL}{self.i}/review/", {"status": "approved"}, format="json")

    def put(self, data, c=None, name="m.glb"):
        return (c or self.co).post(f"{URL}{self.i}/model/", {"file": SimpleUploadedFile(name, data)}, format="multipart")

    def test_valid_glb_is_stored_and_downloaded_back_unchanged(self):
        data = make_glb()
        r = self.put(data)
        self.assertEqual((r.status_code, r.data["model_source"], r.data["status"]), (200, "uploaded", "pending"))
        d = self.co.get(f"{URL}{self.i}/export/glb/")
        self.assertEqual((d.status_code, b"".join(d.streaming_content)), (200, data))

    def test_invalid_glb_files_are_refused_with_a_reason(self):
        for bad, why in ((b"hello world, not glb at all....", "GLB"), (make_glb()[:-4], "truncated"),
                         (make_glb({"asset": {"version": "2.0"}, "meshes": [{}], "buffers": [{"uri": "http://evil.example/x.bin"}]}), "external"),
                         (make_glb({"asset": {"version": "2.0"}}), "no meshes"), (make_glb({"asset": {"version": "1.0"}, "meshes": [{}]}), "2.0")):
            r = self.put(bad)
            self.assertEqual(r.status_code, 400, why)
            self.assertIn("file", r.data["error"]["fields"] if "error" in r.data else r.data)
        self.assertEqual(T.objects.get(pk=self.i).glb_file.name, "")

    def test_parametric_models_export_as_glb_and_gltf_for_any_visible_item(self):
        g = self.ch.get(f"{URL}{self.i}/export/glb/")
        self.assertEqual((g.status_code, g.content[:4]), (200, b"glTF"))
        self.assertTrue(json.loads(self.ch.get(f"{URL}{self.i}/export/gltf/").content)["asset"]["version"] == "2.0")

    def test_only_owner_uploads_and_removal_returns_to_generated(self):
        self.assertEqual(self.put(make_glb(), c=self.cp).status_code, 403)
        self.put(make_glb())
        r = self.co.delete(f"{URL}{self.i}/model/")
        self.assertEqual(r.data["model_source"], "parametric")

    def test_glb_validator_directly(self):
        self.assertEqual(glb.validate_glb(make_glb())["meshes"], 1)
        with self.assertRaises(glb.GlbError):
            glb.validate_glb(b"")
        with self.assertRaises(glb.GlbError):
            glb.validate_glb(b"x" * (glb.MAX_BYTES + 1))
