import struct
from io import BytesIO

from django.test import TestCase
from openpyxl import load_workbook

from apps.core.tests.helpers import CAB, client_for, make_user

CL = "/api/v1/cutting-lists/"


class CalcApiTests(TestCase):
    def setUp(self):
        self.c = client_for(make_user())

    def test_material_calculation(self):
        r = self.c.post("/api/v1/calculations/material/", CAB, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertGreater(r.data["summary"]["total_area_m2"], 5)
        self.assertNotIn("saved_id", r.data)

    def test_validation_errors_are_400(self):
        r = self.c.post("/api/v1/calculations/material/", dict(CAB, width=-5), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("width", r.data["error"]["fields"])
        self.assertEqual(self.c.post("/api/v1/calculations/material/", {"width": "abc"}, format="json").status_code, 400)

    def test_save_and_list_isolated(self):
        cid = self.c.post("/api/v1/calculations/material/", dict(CAB, save=True, name="Mine"), format="json").data["saved_id"]
        self.assertEqual(self.c.get(f"/api/v1/calculations/{cid}/").status_code, 200)
        other = client_for(make_user("o@x.com"))
        self.assertEqual(other.get(f"/api/v1/calculations/{cid}/").status_code, 404)
        self.assertEqual(other.get("/api/v1/calculations/").data["count"], 0)

    def test_cutting_list_optimize_export(self):
        r = self.c.post(CL + "from-calculation/", dict(CAB, name="Wardrobe"), format="json")
        self.assertEqual(r.status_code, 201, r.data)
        cid = r.data["id"]
        self.assertEqual(len(r.data["parts"]), 6)
        o = self.c.post(f"{CL}{cid}/optimize/", {}, format="json")
        self.assertEqual(o.status_code, 201, o.data)
        s = o.data["result"]["summary"]
        self.assertGreaterEqual(s["sheet_count"], 2)  # MDF group + HDF group
        self.assertEqual(s["unplaced_count"], 0)
        pdf = self.c.get(f"{CL}{cid}/export/pdf/")
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        wb = load_workbook(BytesIO(self.c.get(f"{CL}{cid}/export/xlsx/").content))
        self.assertIn("Optimization", wb.sheetnames)
        self.assertIn("PROFESSIONAL REVIEW", wb["Cutting list"]["A2"].value)
        other = client_for(make_user("o@x.com"))
        self.assertEqual(other.get(f"{CL}{cid}/").status_code, 404)
        self.assertEqual(other.get(f"{CL}{cid}/export/pdf/").status_code, 404)
        self.assertEqual(other.post(f"{CL}{cid}/optimize/", {}, format="json").status_code, 404)

    def test_manual_cutting_list_and_update_replaces_parts(self):
        part = {"name": "A", "width": 300, "height": 600, "thickness": 18, "quantity": 4, "material": "MDF"}
        r = self.c.post(CL, {"name": "Manual", "parts": [part]}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["totals"]["pieces"], 4)
        r = self.c.patch(f"{CL}{r.data['id']}/", {"parts": [dict(part, name="B", quantity=1)]}, format="json")
        self.assertEqual([p["name"] for p in r.data["parts"]], ["B"])
        self.assertEqual(self.c.post(CL, {"name": "x", "parts": [dict(part, width=5)]}, format="json").status_code, 400)
        empty = self.c.post(CL, {"name": "empty"}, format="json")
        self.assertEqual(self.c.post(f"{CL}{empty.data['id']}/optimize/", {}, format="json").status_code, 400)

    def test_oversized_part_reported_in_optimization(self):
        part = {"name": "Huge", "width": 3000, "height": 3000, "thickness": 18, "quantity": 1, "material": "MDF"}
        cid = self.c.post(CL, {"name": "Big", "parts": [part]}, format="json").data["id"]
        r = self.c.post(f"{CL}{cid}/optimize/", {}, format="json")
        self.assertEqual(r.data["result"]["summary"]["unplaced_count"], 1)

    def test_geometry_endpoints(self):
        r = self.c.post("/api/v1/geometry/preview/", dict(CAB, color="#112233"), format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["boxes"][0]["color"], "#112233")
        self.assertEqual(self.c.post("/api/v1/geometry/preview/", dict(CAB, color="red"), format="json").status_code, 400)
        g = self.c.post("/api/v1/geometry/export/glb/", CAB, format="json")
        self.assertEqual(g.status_code, 200)
        self.assertEqual(struct.unpack("<I", g.content[:4])[0], 0x46546C67)
        self.assertEqual(self.c.post("/api/v1/geometry/export/fbx/", CAB, format="json").status_code, 400)
        self.assertEqual(self.c.post("/api/v1/geometry/export/obj/", CAB, format="json").status_code, 200)
