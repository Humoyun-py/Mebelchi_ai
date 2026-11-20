import json
import struct

from django.test import SimpleTestCase

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
