"""Handles, colours and the proof that the 3D model is the calculated cabinet."""
import json
import random
import struct

from django.test import SimpleTestCase

from apps.calculations import engine
from apps.geometry import builder, exporters
from apps.geometry.colors import clean_colors

BASE = dict(width=900, height=2000, depth=500, thickness=18, shelves=2, doors=2, drawers=2)


def named(g, prefix):
    return [b for b in g["boxes"] if b["name"].startswith(prefix)]


class HandleStyleTests(SimpleTestCase):
    def test_bar_is_the_default_and_matches_the_hardware_list(self):
        g = builder.build_cabinet(BASE)
        handles = [b for b in g["boxes"] if "handle" in b["name"].lower()]
        self.assertEqual(len(handles), 4)                                                        # 2 doors + 2 drawers
        self.assertEqual({h["name"]: h["quantity"] for h in engine.calculate(BASE)["hardware"]}["Handle"], 4)

    def test_knob_handles_are_small_cubes_at_the_same_places(self):
        g = builder.build_cabinet(dict(BASE, handle_style="knob"))
        knobs = [b for b in g["boxes"] if "handle" in b["name"].lower()]
        self.assertEqual(len(knobs), 4)
        for k in knobs:
            self.assertEqual((k["sx"], k["sy"], k["sz"]), builder.KNOB)
        self.assertEqual(g["bounds"]["max"][2], 500 + 18 + 22)

    def test_none_removes_handles_from_the_model_and_the_hardware(self):
        g = builder.build_cabinet(dict(BASE, handle_style="none"))
        self.assertFalse([b for b in g["boxes"] if "handle" in b["name"].lower()])
        self.assertNotIn("Handle", {h["name"] for h in engine.calculate(dict(BASE, handle_style="none"))["hardware"]})

    def test_invalid_style_is_rejected(self):
        with self.assertRaises(engine.EngineValidationError) as cm:
            builder.build_cabinet(dict(BASE, handle_style="gold"))
        self.assertIn("handle_style", cm.exception.errors)

    def test_default_output_is_unchanged_for_existing_callers(self):
        """A caller that knows nothing about handle styles gets exactly the previous boxes and bounds."""
        g = builder.build_cabinet(BASE)
        self.assertEqual(g["bounds"]["max"], [900, 2000, 500 + 18 + 12])
        bar = next(b for b in g["boxes"] if b["name"] == "Door handle 1")
        self.assertEqual((bar["sx"], bar["sy"], bar["sz"]), (8, 120, 12))

    def test_bar_handles_never_overhang_small_fronts(self):
        g = builder.build_cabinet(dict(width=600, height=720, depth=560, doors=1, drawers=1, cabinet_type="kitchen_base"))
        door, bar = next(b for b in g["boxes"] if b["name"] == "Door 1"), next(b for b in g["boxes"] if b["name"] == "Door handle 1")
        self.assertLessEqual(bar["sy"], door["sy"] - 40 + 1e-6)
        self.assertGreaterEqual(bar["y"], door["y"]); self.assertLessEqual(bar["y"] + bar["sy"], door["y"] + door["sy"])


class ColourTests(SimpleTestCase):
    def test_groups_are_painted_independently(self):
        g = builder.build_cabinet(BASE, colors={"carcass": "#112233", "fronts": "#445566", "back": "#778899", "handle": "#aabbcc"})
        by_kind = {}
        for b in g["boxes"]:
            by_kind.setdefault(b["kind"], set()).add(b["color"])
        self.assertEqual(by_kind["carcass"], {"#112233"}); self.assertEqual(by_kind["shelf"], {"#112233"})
        self.assertEqual(by_kind["door"], {"#445566"}); self.assertEqual(by_kind["drawer"], {"#445566"})
        self.assertEqual(by_kind["back"], {"#778899"}); self.assertEqual(by_kind["handle"], {"#aabbcc"})

    def test_group_colours_win_over_the_legacy_single_colour(self):
        g = builder.build_cabinet(BASE, color="#111111", colors={"fronts": "#222222"})
        self.assertEqual({b["color"] for b in g["boxes"] if b["kind"] in ("carcass", "shelf")}, {"#111111"})
        self.assertEqual({b["color"] for b in g["boxes"] if b["kind"] in ("door", "drawer")}, {"#222222"})

    def test_unpainted_groups_keep_their_defaults(self):
        g = builder.build_cabinet(BASE, colors={"fronts": "#222222"})
        self.assertEqual(next(b for b in g["boxes"] if b["kind"] == "back")["color"], builder.KIND_COLORS["back"])
        self.assertEqual(next(b for b in g["boxes"] if b["kind"] == "handle")["color"], builder.KIND_COLORS["handle"])

    def test_validation(self):
        self.assertEqual(clean_colors({"fronts": "#ABCDEF"}), {"fronts": "#abcdef"})
        self.assertEqual(clean_colors(None), {})
        for bad in ({"fronts": "red"}, {"fronts": "#12345"}, {"doors": "#112233"}, {"fronts": 5}, ["#112233"], "x", {"fronts": "#12345g"}):
            with self.assertRaises(ValueError, msg=bad):
                clean_colors(bad)

    def test_exports_carry_the_colours(self):
        g = builder.build_cabinet(BASE, colors={"fronts": "#ff0000"})
        doc = json.loads(exporters.to_gltf(g["boxes"]))
        reds = [m for m in doc["materials"] if m["pbrMetallicRoughness"]["baseColorFactor"][:3] == [1.0, 0.0, 0.0]]
        self.assertTrue(reds)
        glb = exporters.to_glb(g["boxes"])
        jl, _ = struct.unpack("<II", glb[12:20])
        self.assertIn("1.0, 0.0, 0.0", json.dumps(json.loads(glb[20:20 + jl])["materials"]).replace("[1.0,0.0,0.0", "1.0, 0.0, 0.0").replace("[1.0, 0.0, 0.0", "1.0, 0.0, 0.0"))


class ConsistencyTests(SimpleTestCase):
    """The model must be the calculated cabinet: sizes, counts and positions all follow the calculation."""

    def check(self, **kw):
        inp = dict(BASE, **kw)
        g = builder.build_cabinet(inp, verify=True)
        return g, g["consistency"]

    def test_every_type_is_consistent(self):
        cases = [BASE, dict(width=600, height=720, depth=560, doors=1, shelves=1, drawers=0, cabinet_type="kitchen_base"),
                 dict(width=600, height=720, depth=560, doors=0, shelves=0, drawers=3, cabinet_type="kitchen_base"),
                 dict(width=800, height=720, depth=320, doors=2, shelves=1, drawers=0, cabinet_type="kitchen_wall"),
                 dict(width=1800, height=2300, depth=600, doors=3, shelves=2, drawers=0, cabinet_type="sliding_wardrobe"),
                 dict(width=1800, height=2300, depth=600, doors=4, shelves=0, drawers=0, cabinet_type="sliding_wardrobe", handle_style="none")]
        for c in cases:
            g = builder.build_cabinet(c, verify=True)
            self.assertEqual(g["consistency"]["problems"], [], c)
            self.assertTrue(g["consistency"]["valid"])
            self.assertIn("drawer boxes", " ".join(g["consistency"]["not_modelled"]))

    def tamper(self, mutate, **kw):
        inp = engine.CabinetInput.from_dict(dict(BASE, **kw))
        g = builder.build_cabinet(inp)
        mutate(g["boxes"])
        return builder.check_consistency(g, inp, engine.calculate(inp)["parts"])

    def test_a_wrong_size_is_detected(self):
        def shrink_door(bs):
            next(b for b in bs if b["name"] == "Door 1")["sy"] -= 5
        r = self.tamper(shrink_door)
        self.assertFalse(r["valid"]); self.assertTrue(any("'Door 1'" in p and "calculated part 'Door'" in p for p in r["problems"]), r["problems"])

    def test_a_missing_component_is_detected(self):
        r = self.tamper(lambda bs: bs.remove(next(b for b in bs if b["name"] == "Shelf 2")))
        self.assertTrue(any("1 shelves modelled, 2 calculated" in p for p in r["problems"]), r["problems"])
        r = self.tamper(lambda bs: bs.remove(next(b for b in bs if b["name"] == "Door handle 1")))
        self.assertTrue(any("handles modelled" in p for p in r["problems"]), r["problems"])

    def test_overall_size_drift_is_detected(self):
        def stretch(bs):
            for b in bs:
                if b["name"] == "Right side":
                    b["x"] += 30
        r = self.tamper(stretch)
        self.assertTrue(any("model width" in p for p in r["problems"]), r["problems"])

    def test_overlapping_components_are_detected(self):
        def collide(bs):
            s2 = next(b for b in bs if b["name"] == "Shelf 2"); s1 = next(b for b in bs if b["name"] == "Shelf 1")
            s2["y"] = s1["y"] + 5
        r = self.tamper(collide)
        self.assertTrue(any("'Shelf 1' and 'Shelf 2' occupy the same space" in p for p in r["problems"]), r["problems"])

    def test_touching_is_not_overlapping(self):
        self.assertEqual(self.check()[1]["problems"], [])      # back panel, doors and drawer fronts all touch the carcass planes

    def test_random_valid_cabinets_are_always_consistent(self):
        rng = random.Random(20261125)
        tried = 0
        for _ in range(2500):
            t = rng.choice(engine.CABINET_TYPES)
            d = dict(width=rng.randint(200, 4000), height=rng.randint(200, 3000), depth=rng.randint(150, 1000), thickness=rng.choice([8, 16, 18, 22, 30, 40]),
                     shelves=rng.randint(0, 12), doors=rng.randint(0, 6), drawers=rng.randint(0, 6) if t in ("standard", "kitchen_base") else 0, cabinet_type=t,
                     handle_style=rng.choice(engine.HANDLE_STYLES), edge_thickness=rng.choice([0, 0.4, 1]), sliding_overlap=rng.choice([10, 30, 50, 100]),
                     rail_width=rng.choice([50, 100, 300]), plinth_height=rng.choice([60, 100, 200]))
            try:
                g = builder.build_cabinet(d, verify=True)
            except engine.EngineValidationError:
                continue
            tried += 1
            self.assertEqual(g["consistency"]["problems"], [], d)
        self.assertGreater(tried, 800)     # the generator really exercises valid cabinets


class PhysicalRuleTests(SimpleTestCase):
    """Rules found by the consistency property test: impossible cabinets are refused instead of drawn."""

    def errs(self, **kw):
        with self.assertRaises(engine.EngineValidationError) as cm:
            engine.calculate(dict(width=900, height=1000, depth=500, **kw))
        return cm.exception.errors

    def test_shelves_may_not_be_closer_than_30_mm(self):
        self.assertIn("shelves", self.errs(shelves=20))
        engine.calculate(dict(width=900, height=1000, depth=500, shelves=5))

    def test_top_rails_may_not_overlap(self):
        with self.assertRaises(engine.EngineValidationError) as cm:
            engine.calculate(dict(width=600, height=720, depth=150, cabinet_type="kitchen_base", rail_width=100))
        self.assertIn("rail_width", cm.exception.errors)

    def test_hanging_rail_must_fit_inside_the_cabinet(self):
        with self.assertRaises(engine.EngineValidationError) as cm:
            engine.calculate(dict(width=800, height=300, depth=320, cabinet_type="kitchen_wall", rail_width=300))
        self.assertIn("rail_width", cm.exception.errors)

    def test_sliding_shelves_clear_both_door_lanes(self):
        r = engine.calculate(dict(width=1800, height=2300, depth=600, doors=3, shelves=2, cabinet_type="sliding_wardrobe"))
        shelf = next(p for p in r["parts"] if p["name"] == "Shelf")
        self.assertEqual(shelf["height"], 600 - 20 - 2 * 18 - 4 - 5)       # 535: behind the rear lane
        g = builder.build_cabinet(dict(width=1800, height=2300, depth=600, doors=3, shelves=2, cabinet_type="sliding_wardrobe"))
        rear_lane_back = min(b["z"] for b in g["boxes"] if b["kind"] == "door")
        for s in named(g, "Shelf"):
            self.assertLessEqual(s["z"] + s["sz"], rear_lane_back - 5 + 1e-6)

    def test_sliding_panels_in_the_same_lane_cannot_collide(self):
        with self.assertRaises(engine.EngineValidationError) as cm:
            engine.calculate(dict(width=600, height=2300, depth=600, doors=6, cabinet_type="sliding_wardrobe", sliding_overlap=100))
        self.assertIn("sliding_overlap", cm.exception.errors)

    def test_hanging_rail_collision_with_a_shelf_is_disclosed(self):
        r = engine.calculate(dict(width=800, height=400, depth=320, cabinet_type="kitchen_wall", shelves=6, rail_width=100))
        self.assertTrue(any("collides with the hanging rail" in w for w in r["warnings"]))
