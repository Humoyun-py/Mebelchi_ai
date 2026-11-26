import json

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase

from apps.core.tests.helpers import client_for, make_user
from apps.designs.models import Design
from apps.rooms import mebelchi
from apps.rooms.models import RoomFlow
from apps.rooms.services import MAX_ACTIVE_FLOWS
from apps.rooms.tests.test_api import DOOR, SIZE, WINDOW, RoomApiBase

URL = "/api/v1/rooms/"


class FileTests(SimpleTestCase):
    CFG = {"schema": "room.v1", "goal": "bedroom", "style": "modern", "room": {"width": 4000, "length": 3000, "height": 2700}, "openings": [],
           "items": [{"id": "a1", "template": "bedside", "name": "Bedside table", "x": 100, "z": 100, "rot": 0, "width": 450, "depth": 400, "height": 500,
                      "shelves": 0, "doors": 0, "drawers": 2, "color": "#e5e7eb"}], "colors": {"wall": "#cbd5e1", "floor": "#d6c9b4", "item": "#e5e7eb"}}

    def doc(self, **over):
        d = mebelchi.build("My room", self.CFG)
        body = {k: v for k, v in d.items() if k != "checksum"}
        body.update(over)
        return {**body, "checksum": {"alg": "sha256", "value": mebelchi._digest(body)}}

    def test_round_trip_keeps_room_furniture_colours_and_camera(self):
        cfg = {**self.CFG, "camera": {"position": [1, 2, 3], "target": [0, 1, 0], "fov": 60}, "light": {"intensity": 1.5, "warm": True}, "floor_material": "tile"}
        out = mebelchi.parse(mebelchi.dumps(mebelchi.build("Roundtrip", cfg)))
        self.assertEqual(out["name"], "Roundtrip")
        c = out["config"]
        self.assertEqual((c["room"], c["items"][0]["x"], c["colors"]["wall"], c["floor_material"]), (cfg["room"], 100, "#cbd5e1", "tile"))
        self.assertEqual((c["camera"]["fov"], c["light"]), (60.0, {"intensity": 1.5, "warm": True}))

    def test_document_lists_models_and_says_it_is_not_protection(self):
        d = mebelchi.build("x", self.CFG)
        self.assertEqual(d["models"], ["bedside"])
        self.assertIn("not copy protection", d["notice"])
        self.assertEqual((d["format"], d["version"]), ("mebelchi", 1))

    def test_edited_or_damaged_files_are_refused(self):
        d = mebelchi.build("x", self.CFG)
        d["room"] = {"width": 9000, "length": 3000, "height": 2700}
        with self.assertRaises(mebelchi.MebelchiError) as cm:
            mebelchi.parse(d)
        self.assertIn("checksum", cm.exception.errors)

    def test_not_a_project_file(self):
        for raw in (b"not json", b"[]", json.dumps({"format": "other"}), json.dumps({"format": "mebelchi", "version": 9}).encode()):
            with self.assertRaises(mebelchi.MebelchiError):
                mebelchi.parse(raw)

    def test_too_large(self):
        with self.assertRaises(mebelchi.MebelchiError):
            mebelchi.parse(b" " * (mebelchi.MAX_BYTES + 1))

    def test_valid_checksum_does_not_excuse_impossible_data(self):
        cases = {"room.width": self.doc(room={"width": 10, "length": 3000, "height": 2700}),
                 "style": self.doc(style="rococo"), "goal": self.doc(goal="garage"),
                 "colors.wall": self.doc(colors={"wall": "red"}), "furniture.0.position": self.doc(furniture=[{**self.CFG["items"][0], "x": 3900}]),
                 "camera.fov": self.doc(camera={"position": [0, 0, 0], "target": [0, 0, 0], "fov": 500}),
                 "floor_material": self.doc(floor_material="lava"), "furniture": self.doc(furniture="chair")}
        for key, d in cases.items():
            with self.assertRaises(mebelchi.MebelchiError, msg=key) as cm:
                mebelchi.parse(d)
            self.assertTrue(any(key.split(".")[0] in k for k in cm.exception.errors), (key, cm.exception.errors))

    def test_overlapping_furniture_is_refused(self):
        other = {**self.CFG["items"][0], "id": "b2", "x": 200, "z": 200}
        with self.assertRaises(mebelchi.MebelchiError) as cm:
            mebelchi.parse(self.doc(furniture=[self.CFG["items"][0], other]))
        self.assertIn("furniture.1.position", cm.exception.errors)


class ApiTests(RoomApiBase):
    def built(self, c=None):
        rid = self.start(c)
        self.answer(rid, "goal", "bedroom", c)
        self.answer(rid, "photo", {"skip": True}, c)
        self.answer(rid, "elements", {"doors": 1, "windows": 1, "furniture": ["bedside", "dresser"]}, c)
        self.answer(rid, "size", SIZE, c)
        self.answer(rid, "openings", [DOOR, WINDOW], c)
        self.answer(rid, "style", "classic", c)
        return rid

    def test_export_then_import_makes_an_equal_copy(self):
        rid = self.built()
        r = self.ca.get(f"{URL}{rid}/export/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(".mebelchi", r["Content-Disposition"])
        copy = self.ca.post(f"{URL}import/", {"file": SimpleUploadedFile("room.mebelchi", r.content)}, format="multipart")
        self.assertEqual(copy.status_code, 201, copy.data)
        orig = self.ca.get(f"{URL}{rid}/").data["room"]["config"]
        new = copy.data["room"]["config"]
        for k in ("room", "openings", "items", "style", "goal", "colors"):
            self.assertEqual(new[k], orig[k], k)
        self.assertNotEqual(copy.data["id"], rid)
        self.assertEqual((copy.data["step"], copy.data["unknown_models"]), ("furnish", []))
        self.assertEqual(self.ca.get(f"{URL}{copy.data['id']}/model/").status_code, 200)

    def test_another_user_can_import_the_file_but_not_open_the_original(self):
        rid = self.built()
        body = self.ca.get(f"{URL}{rid}/export/").content
        self.assertEqual(self.cb.get(f"{URL}{rid}/export/").status_code, 404)
        r = self.cb.post(f"{URL}import/", {"file": SimpleUploadedFile("r.mebelchi", body)}, format="multipart")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Design.objects.get(pk=r.data["design"]).owner_id, self.b.id)

    def test_import_as_json_body_and_bad_files(self):
        rid = self.built()
        doc = json.loads(self.ca.get(f"{URL}{rid}/export/").content)
        self.assertEqual(self.ca.post(f"{URL}import/", doc, format="json").status_code, 201)
        doc["room"]["width"] = 5000
        r = self.ca.post(f"{URL}import/", doc, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("checksum", str(r.data))
        self.assertEqual(self.ca.post(f"{URL}import/", {}, format="json").status_code, 400)
        self.assertEqual(self.ca.post(f"{URL}import/", {"file": SimpleUploadedFile("x.mebelchi", b"junk")}, format="multipart").status_code, 400)

    def test_unknown_models_are_reported_not_fatal(self):
        cfg = FileTests.CFG
        item = {**cfg["items"][0], "template": "from-another-server"}
        d = mebelchi.build("Foreign", {**cfg, "items": [item]})
        r = self.ca.post(f"{URL}import/", d, format="json")
        self.assertEqual((r.status_code, r.data["unknown_models"]), (201, ["from-another-server"]))

    def test_login_required_and_flow_limit(self):
        from rest_framework.test import APIClient
        self.assertEqual(APIClient().post(f"{URL}import/", {}, format="json").status_code, 401)
        d = mebelchi.build("x", FileTests.CFG)
        for _ in range(MAX_ACTIVE_FLOWS):
            RoomFlow.objects.create(owner=self.a)
        self.assertEqual(self.ca.post(f"{URL}import/", d, format="json").status_code, 409)

    def test_export_before_the_room_exists_is_409(self):
        rid = self.start()
        self.assertEqual(self.ca.get(f"{URL}{rid}/export/").status_code, 409)

    def test_glb_export_is_a_real_glb(self):
        rid = self.built()
        r = self.ca.get(f"{URL}{rid}/export-glb/")
        self.assertEqual((r.status_code, r.content[:4]), (200, b"glTF"))
        self.assertEqual(self.cb.get(f"{URL}{rid}/export-glb/").status_code, 404)

    def test_settings_change_colours_light_camera_and_floor_material(self):
        rid = self.built()
        r = self.ca.patch(f"{URL}{rid}/settings/", {"wall": "#ffffff", "floor": "#222222", "floor_material": "tile", "light": {"intensity": 1.4, "warm": True},
                                                  "camera": {"position": [0, 1.6, 0], "target": [1, 1.6, 0], "fov": 70}}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        c = r.data["room"]["config"]
        self.assertEqual((c["colors"]["wall"], c["colors"]["floor"], c["floor_material"], c["light"]["warm"]), ("#ffffff", "#222222", "tile", True))
        boxes = self.ca.get(f"{URL}{rid}/model/").data["boxes"]
        self.assertEqual(next(b for b in boxes if b["kind"] == "floor")["color"], "#222222")
        self.assertEqual(self.ca.get(f"{URL}{rid}/export/").status_code, 200)

    def test_settings_validation_and_ownership(self):
        rid = self.built()
        for body in ({}, {"wall": "red"}, {"floor_material": "lava"}, {"light": {"intensity": 9}}, {"camera": {"fov": 1}}, {"bogus": 1}):
            self.assertEqual(self.ca.patch(f"{URL}{rid}/settings/", body, format="json").status_code, 400, body)
        self.assertEqual(self.cb.patch(f"{URL}{rid}/settings/", {"wall": "#ffffff"}, format="json").status_code, 404)
        self.assertEqual(self.ca.patch(f"{URL}{self.start()}/settings/", {"wall": "#ffffff"}, format="json").status_code, 409)   # room not built yet
