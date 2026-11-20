from django.test import SimpleTestCase

from apps.calculations import engine


class EngineTests(SimpleTestCase):
    base = dict(width=800, height=2000, depth=400, thickness=18, shelves=3, doors=2, drawers=0)

    def test_parts_dimensions(self):
        r = engine.calculate(self.base)
        parts = {p["name"]: p for p in r["parts"]}
        self.assertEqual((parts["Side panel"]["width"], parts["Side panel"]["height"], parts["Side panel"]["quantity"]), (400, 2000, 2))
        self.assertEqual(parts["Top panel"]["width"], 764)          # 800 - 2*18
        self.assertEqual(parts["Shelf"]["height"], 380)             # depth - 20 setback
        self.assertEqual(parts["Shelf"]["quantity"], 3)
        self.assertEqual(parts["Back panel"]["material"], "HDF")
        self.assertAlmostEqual(parts["Door"]["width"], 396.5)       # (800 - 4 - 3) / 2
        self.assertTrue(r["requires_professional_review"])
        self.assertTrue(r["assumptions"])

    def test_area_matches_parts(self):
        r = engine.calculate(self.base)
        manual = sum(p["width"] * p["height"] * p["quantity"] for p in r["parts"]) / 1e6
        self.assertAlmostEqual(r["summary"]["total_area_m2"], manual, places=3)

    def test_drawers_and_doors_share_height(self):
        r = engine.calculate(dict(width=900, height=2000, depth=500, thickness=18, shelves=1, doors=2, drawers=3))
        lay = r["summary"]["layout"]
        self.assertGreater(lay["door_h"], 100)
        zone = 3 * (lay["drawer_front_h"] + 3)
        self.assertLessEqual(lay["door_y"] + lay["door_h"] + 2, 2000 + 1e-6)
        self.assertGreaterEqual(lay["door_y"], zone)
        names = [p["name"] for p in r["parts"]]
        self.assertIn("Drawer front", names)
        self.assertEqual({p["name"]: p["quantity"] for p in r["parts"]}["Drawer side"], 6)

    def test_rejects_out_of_range(self):
        for bad in (dict(self.base, width=-1), dict(self.base, width=10), dict(self.base, thickness=100), dict(self.base, doors=9),
                    dict(self.base, shelves=-1)):
            with self.assertRaises(engine.EngineValidationError):
                engine.calculate(bad)

    def test_rejects_non_numeric_and_bool(self):
        with self.assertRaises(engine.EngineValidationError):
            engine.calculate(dict(self.base, width="800"))
        with self.assertRaises(engine.EngineValidationError):
            engine.calculate(dict(self.base, shelves=True))
        with self.assertRaises(engine.EngineValidationError):
            engine.calculate(dict(self.base, shelves=1.5))

    def test_rejects_impossible_geometry(self):
        with self.assertRaises(engine.EngineValidationError):
            engine.calculate(dict(width=300, height=2000, depth=400, doors=6))
        with self.assertRaises(engine.EngineValidationError):
            engine.calculate(dict(width=800, height=600, depth=400, drawers=10))

    def test_warnings(self):
        r = engine.calculate(dict(width=1500, height=2000, depth=400, thickness=18, shelves=2, doors=1))
        self.assertTrue(any("Door width" in w for w in r["warnings"]))
        self.assertTrue(any("sag" in w for w in r["warnings"]))
