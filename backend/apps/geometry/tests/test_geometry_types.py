from django.test import SimpleTestCase

from apps.calculations import engine
from apps.geometry import builder


def boxes_of(g, prefix):
    return [b for b in g["boxes"] if b["name"].startswith(prefix) and "handle" not in b["name"].lower()]


class GeometryMatchesCalculationTests(SimpleTestCase):
    """The 3D model must be built from exactly the dimensions the calculation reports."""

    def test_sliding_wardrobe(self):
        cab = dict(width=1800, height=2300, depth=600, shelves=2, doors=3, cabinet_type="sliding_wardrobe")
        g, calc = builder.build_cabinet(cab), engine.calculate(cab)
        doors = boxes_of(g, "Sliding door")
        part = next(p for p in calc["parts"] if p["name"] == "Sliding door")
        self.assertEqual(len(doors), part["quantity"])
        for d in doors:
            self.assertEqual((d["sx"], d["sy"], d["sz"]), (part["width"], part["height"], part["thickness"]))
        # the panels together span exactly the internal width: left edge of first .. right edge of last
        left = min(d["x"] for d in doors)
        right = max(d["x"] + d["sx"] for d in doors)
        self.assertAlmostEqual(left, 18)
        self.assertAlmostEqual(right, 1800 - 18)
        # neighbouring panels overlap in plan by the configured overlap and sit in different lanes (no collision)
        doors.sort(key=lambda d: d["x"])
        for a, b in zip(doors, doors[1:]):
            self.assertAlmostEqual(a["x"] + a["sx"] - b["x"], 30)
            self.assertNotEqual(a["z"], b["z"])
            self.assertGreaterEqual(abs(a["z"] - b["z"]), 18)  # lane pitch >= panel thickness: they cannot intersect
        self.assertEqual({b["name"] for b in g["boxes"]} & {"Top track", "Bottom track"}, {"Top track", "Bottom track"})
        for b in g["boxes"]:
            self.assertGreaterEqual(b["z"], -4 - 0.01)
            self.assertLessEqual(b["z"] + b["sz"], 600 + 18 + 12 + 0.01)

    def test_kitchen_base_stands_on_the_plinth(self):
        cab = dict(width=600, height=720, depth=560, shelves=1, doors=1, drawers=0, cabinet_type="kitchen_base")
        g = builder.build_cabinet(cab)
        side = next(b for b in g["boxes"] if b["name"] == "Left side")
        self.assertEqual((side["y"], side["sy"]), (100, 620))
        plinth = next(b for b in g["boxes"] if b["name"] == "Plinth")
        self.assertEqual((plinth["y"], plinth["sy"], plinth["sx"]), (0, 100, 600))
        self.assertEqual(len(boxes_of(g, "Front top rail")) + len(boxes_of(g, "Rear top rail")), 2)
        self.assertNotIn("Top", [b["name"] for b in g["boxes"]])
        door = next(b for b in g["boxes"] if b["name"] == "Door 1")
        self.assertEqual((door["y"], door["sy"]), (102, 616))
        self.assertAlmostEqual(max(b["y"] + b["sy"] for b in g["boxes"]), 720)  # total height is the requested height
        self.assertGreaterEqual(min(b["y"] for b in g["boxes"]), 0)

    def test_kitchen_base_drawers_start_above_plinth(self):
        g = builder.build_cabinet(dict(width=600, height=720, depth=560, drawers=2, cabinet_type="kitchen_base"))
        fronts = sorted(boxes_of(g, "Drawer front"), key=lambda b: b["y"])
        self.assertGreater(fronts[0]["y"], 100)
        calc_front = next(p for p in engine.calculate(dict(width=600, height=720, depth=560, drawers=2, cabinet_type="kitchen_base"))["parts"]
                          if p["name"] == "Drawer front")
        self.assertEqual(fronts[0]["sy"], calc_front["height"])

    def test_kitchen_wall_has_hanging_rail(self):
        g = builder.build_cabinet(dict(width=800, height=720, depth=320, doors=2, cabinet_type="kitchen_wall"))
        rail = next(b for b in g["boxes"] if b["name"] == "Hanging rail")
        self.assertEqual((rail["sx"], rail["sy"], rail["sz"]), (764, 100, 18))
        self.assertAlmostEqual(rail["y"] + rail["sy"], 720 - 18)  # directly below the top panel

    def test_standard_cabinet_is_unchanged_by_the_new_code(self):
        g = builder.build_cabinet(dict(width=900, height=2000, depth=500, shelves=2, doors=2, drawers=2))
        names = [b["name"] for b in g["boxes"]]
        self.assertEqual(names[:5], ["Left side", "Right side", "Bottom", "Top", "Back"])

    def test_invalid_types_are_rejected_by_the_builder(self):
        with self.assertRaises(engine.EngineValidationError):
            builder.build_cabinet(dict(width=1800, height=2300, depth=600, doors=1, cabinet_type="sliding_wardrobe"))
