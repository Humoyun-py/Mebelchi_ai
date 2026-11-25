import json
import struct

from django.test import SimpleTestCase, TestCase

from apps.geometry import builder, exporters

P = dict(width=900, height=2000, depth=500, thickness=18, shelves=2, doors=2, drawers=2)


class GeometryTests(SimpleTestCase):
    def test_boxes_within_bounds(self):
        g = builder.build_cabinet(P)
        for b in g["boxes"]:
            self.assertGreaterEqual(b["x"], 0)
            self.assertLessEqual(b["x"] + b["sx"], 900 + 0.01)
            self.assertLessEqual(b["y"] + b["sy"], 2000 + 0.01)
        kinds = {b["kind"] for b in g["boxes"]}
        self.assertTrue({"carcass", "door", "drawer", "back", "shelf"} <= kinds)

    def test_counts(self):
        g = builder.build_cabinet(P)
        names = [b["name"] for b in g["boxes"]]
        self.assertEqual(sum(n.startswith("Door ") and "handle" not in n for n in names), 2)
        self.assertEqual(sum(n.startswith("Drawer front") for n in names), 2)
        self.assertEqual(sum(n.startswith("Shelf") for n in names), 2)

    def test_glb_is_valid(self):
        boxes = builder.build_cabinet(P)["boxes"]
        glb = exporters.to_glb(boxes)
        magic, version, length = struct.unpack("<III", glb[:12])
        self.assertEqual((magic, version, length), (0x46546C67, 2, len(glb)))
        jl, jt = struct.unpack("<II", glb[12:20])
        self.assertEqual(jt, 0x4E4F534A)
        doc = json.loads(glb[20:20 + jl])
        self.assertEqual(len(doc["meshes"]), len(boxes))
        self.assertEqual(len(glb) % 4, 0)

    def test_gltf_and_obj(self):
        boxes = builder.build_cabinet(P)["boxes"]
        doc = json.loads(exporters.to_gltf(boxes))
        self.assertTrue(doc["buffers"][0]["uri"].startswith("data:application/octet-stream;base64,"))
        obj = exporters.to_obj(boxes).decode()
        self.assertEqual(obj.count("\no "), len(boxes))
        self.assertEqual(obj.count("\nv "), len(boxes) * 24)
        self.assertEqual(obj.count("\nf "), len(boxes) * 12)


class PreviewApiEditorTests(TestCase):
    URL = "/api/v1/geometry/preview/"

    def post(self, **extra):
        from apps.core.tests.helpers import client_for
        return client_for().post(self.URL, {**P, **extra}, format="json")

    def test_preview_proves_the_model_matches_the_calculation(self):
        r = self.post(cabinet_type="kitchen_base", width=600, height=720, depth=560, shelves=1, doors=1, drawers=0)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data["consistency"]["valid"]); self.assertEqual(r.data["consistency"]["problems"], [])

    def test_handle_style_and_colours_are_applied(self):
        r = self.post(handle_style="none", colors={"fronts": "#ff0000"})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse([b for b in r.data["boxes"] if "handle" in b["name"].lower()])
        self.assertEqual({b["color"] for b in r.data["boxes"] if b["kind"] == "door"}, {"#ff0000"})

    def test_bad_options_are_field_errors(self):
        for body, field in (({"handle_style": "gold"}, "handle_style"), ({"colors": {"fronts": "red"}}, "colors"), ({"colors": {"x": "#112233"}}, "colors"), ({"colors": "red"}, "colors")):
            r = self.post(**body)
            self.assertEqual(r.status_code, 400, body)
            self.assertIn(field, r.data["error"]["fields"])

    def test_exports_respect_style_and_colours_and_do_not_need_verification(self):
        from apps.core.tests.helpers import client_for, make_user
        c = client_for(make_user())
        r = c.post("/api/v1/geometry/export/gltf/", {**P, "handle_style": "none", "colors": {"fronts": "#00ff00"}}, format="json")
        self.assertEqual(r.status_code, 200)
        doc = json.loads(r.content)
        self.assertFalse([n for n in doc["nodes"] if "handle" in n.get("name", "").lower()])
        self.assertTrue([m for m in doc["materials"] if m["pbrMetallicRoughness"]["baseColorFactor"][:3] == [0.0, 1.0, 0.0]])
