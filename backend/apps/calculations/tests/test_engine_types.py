"""Cabinet types, edge-banding cut sizes and pricing. Expected numbers are worked out by hand in the comments."""
from django.test import SimpleTestCase

from apps.calculations import engine
from apps.calculations.engine import EngineValidationError


def parts_of(r):
    return {p["name"]: p for p in r["parts"]}


def hw_of(r):
    return {h["name"]: h["quantity"] for h in r["hardware"]}


class BackwardCompatibilityTests(SimpleTestCase):
    def test_new_parameters_default_to_the_old_behaviour(self):
        base = dict(width=800, height=2000, depth=400, thickness=18, shelves=3, doors=2)
        a = engine.calculate(base)
        b = engine.calculate(dict(base, cabinet_type="standard", edge_thickness=0))
        self.assertEqual(a["parts"], b["parts"])
        self.assertEqual([(p["width"], p["height"]) for p in a["parts"]], [(p["cut_width"], p["cut_height"]) for p in a["parts"]])
        self.assertNotIn("pricing", a)

    def test_unknown_input_keys_are_ignored(self):
        engine.calculate(dict(width=800, height=2000, depth=400, something_else=1))


class KitchenBaseTests(SimpleTestCase):
    # 600 x 720 x 560, 18 mm, plinth 100: carcass height 620, internal width 564, 1 shelf, 1 door
    r = engine.calculate(dict(width=600, height=720, depth=560, shelves=1, doors=1, cabinet_type="kitchen_base"))

    def test_parts(self):
        p = parts_of(self.r)
        self.assertEqual((p["Side panel"]["width"], p["Side panel"]["height"], p["Side panel"]["quantity"]), (560, 620, 2))
        self.assertEqual((p["Front top rail"]["width"], p["Front top rail"]["height"]), (564, 100))
        self.assertEqual((p["Rear top rail"]["width"], p["Rear top rail"]["height"]), (564, 100))
        self.assertNotIn("Top panel", p)
        self.assertEqual((p["Bottom panel"]["width"], p["Bottom panel"]["height"]), (564, 560))
        self.assertEqual((p["Plinth"]["width"], p["Plinth"]["height"]), (600, 100))
        self.assertEqual((p["Shelf"]["width"], p["Shelf"]["height"]), (564, 540))
        self.assertEqual((p["Back panel"]["width"], p["Back panel"]["height"]), (596, 616))
        self.assertEqual((p["Door"]["width"], p["Door"]["height"]), (596, 616))  # 600 - 2*2 ; 620 - 2*2

    def test_layout_sits_on_the_plinth(self):
        lay = self.r["summary"]["layout"]
        self.assertEqual((lay["base_y"], lay["body_h"], lay["door_y"]), (100, 620, 102))
        self.assertAlmostEqual(lay["slot_h"], 292)  # (620 - 36) / 2 slots

    def test_hardware(self):
        h = hw_of(self.r)
        self.assertEqual(h["Adjustable leg"], 4)
        self.assertEqual(h["Hinge"], 2)  # door height 616 <= 900
        self.assertEqual(h["Confirmat screw"], 12)  # 4 joints x ceil(560/200)=3
        self.assertEqual(h["Back panel fixing"], 13)  # ceil(2*(596+616)/200)

    def test_wide_cabinet_gets_centre_legs(self):
        r = engine.calculate(dict(width=1000, height=720, depth=560, doors=2, cabinet_type="kitchen_base"))
        self.assertEqual(hw_of(r)["Adjustable leg"], 6)

    def test_plinth_height_is_configurable_and_validated(self):
        r = engine.calculate(dict(width=600, height=720, depth=560, doors=1, cabinet_type="kitchen_base", plinth_height=150))
        self.assertEqual(parts_of(r)["Side panel"]["height"], 570)
        with self.assertRaises(EngineValidationError):
            engine.calculate(dict(width=600, height=720, depth=560, cabinet_type="kitchen_base", plinth_height=500))
        with self.assertRaises(EngineValidationError) as cm:  # in range (<=200) but leaves < 200 mm of body
            engine.calculate(dict(width=600, height=350, depth=560, cabinet_type="kitchen_base", plinth_height=200))
        self.assertIn("plinth_height", cm.exception.errors)

    def test_drawers_start_above_the_plinth(self):
        r = engine.calculate(dict(width=600, height=720, depth=560, drawers=2, cabinet_type="kitchen_base"))
        self.assertEqual(parts_of(r)["Drawer front"]["quantity"], 2)
        self.assertEqual(r["summary"]["layout"]["base_y"], 100)


class KitchenWallTests(SimpleTestCase):
    r = engine.calculate(dict(width=800, height=720, depth=320, shelves=1, doors=2, cabinet_type="kitchen_wall"))

    def test_parts_and_hardware(self):
        p = parts_of(self.r)
        self.assertEqual((p["Hanging rail"]["width"], p["Hanging rail"]["height"], p["Hanging rail"]["thickness"]), (764, 100, 18))
        self.assertEqual((p["Top panel"]["width"], p["Top panel"]["height"]), (764, 320))
        self.assertEqual((p["Back panel"]["width"], p["Back panel"]["height"]), (796, 716))
        self.assertEqual(p["Door"]["width"], 396.5)  # (800 - 4 - 3) / 2
        h = hw_of(self.r)
        self.assertEqual(h["Wall hanging bracket"], 2)
        self.assertEqual(h["Hinge"], 4)
        self.assertNotIn("Adjustable leg", h)
        self.assertEqual(self.r["warnings"], [])

    def test_deep_wall_cabinet_warns_but_is_allowed(self):
        r = engine.calculate(dict(width=800, height=720, depth=450, cabinet_type="kitchen_wall", doors=2))
        self.assertTrue(any("Wall cabinet depth" in w for w in r["warnings"]))

    def test_no_drawers_on_wall_cabinets(self):
        with self.assertRaises(EngineValidationError) as cm:
            engine.calculate(dict(width=800, height=720, depth=320, cabinet_type="kitchen_wall", drawers=1))
        self.assertIn("drawers", cm.exception.errors)


class SlidingWardrobeTests(SimpleTestCase):
    # 1800 x 2300 x 600, 18 mm, 3 panels, overlap 30, tracks 35 top / 20 bottom, edge tape 0.8
    r = engine.calculate(dict(width=1800, height=2300, depth=600, shelves=2, doors=3, cabinet_type="sliding_wardrobe", edge_thickness=0.8))

    def test_door_geometry(self):
        d = parts_of(self.r)["Sliding door"]
        # internal width 1764: 3 w - 2*30 = 1764  ->  w = 608 ; height 2264 - 35 - 20 = 2209
        self.assertEqual((d["width"], d["height"], d["quantity"]), (608, 2209, 3))
        self.assertEqual(3 * d["width"] - 2 * 30, 1764)
        self.assertNotIn("Door", parts_of(self.r))

    def test_cut_sizes_deduct_tape_on_every_banded_edge(self):
        d = parts_of(self.r)["Sliding door"]
        self.assertAlmostEqual(d["cut_width"], 606.4)    # 608 - 2 * 0.8
        self.assertAlmostEqual(d["cut_height"], 2207.4)  # 2209 - 2 * 0.8
        side = parts_of(self.r)["Side panel"]            # banded on one long edge: closes the width
        self.assertAlmostEqual(side["cut_width"], 599.2)
        self.assertEqual(side["cut_height"], 2300)
        back = parts_of(self.r)["Back panel"]            # not banded
        self.assertEqual((back["cut_width"], back["cut_height"]), (back["width"], back["height"]))

    def test_hardware_has_tracks_and_rollers_but_no_hinges(self):
        h = hw_of(self.r)
        self.assertEqual((h["Sliding track (top)"], h["Sliding track (bottom)"], h["Sliding roller set"], h["Handle"]), (1, 1, 3, 3))
        self.assertNotIn("Hinge", h)

    def test_assumptions_describe_the_type_and_tape(self):
        text = " ".join(self.r["assumptions"])
        self.assertIn("Sliding wardrobe", text)
        self.assertIn("Cut sizes", text)

    def test_track_allowance_is_configurable(self):
        r = engine.calculate(dict(width=1800, height=2300, depth=600, doors=3, cabinet_type="sliding_wardrobe", track_top=50, track_bottom=30))
        self.assertEqual(parts_of(r)["Sliding door"]["height"], 2264 - 80)

    def test_wide_panels_warn(self):
        r = engine.calculate(dict(width=3000, height=2300, depth=600, doors=2, cabinet_type="sliding_wardrobe"))
        self.assertTrue(any("Sliding panel width" in w for w in r["warnings"]))

    def test_rules(self):
        base = dict(width=1800, height=2300, depth=600, cabinet_type="sliding_wardrobe")
        for bad, key in ((dict(doors=1), "doors"), (dict(doors=0), "doors"), (dict(doors=2, drawers=1), "drawers"),
                         (dict(doors=2, thickness=40, depth=150), "depth")):
            with self.assertRaises(EngineValidationError, msg=bad) as cm:
                engine.calculate(dict(base, **bad))
            self.assertIn(key, cm.exception.errors)


class ParameterValidationTests(SimpleTestCase):
    base = dict(width=800, height=2000, depth=400)

    def test_rejects_bad_new_parameters(self):
        for bad in (dict(cabinet_type="spaceship"), dict(edge_thickness=-0.1), dict(edge_thickness=5), dict(sliding_overlap=500),
                    dict(rail_width=10), dict(edge_thickness="0.4"), dict(plinth_height=True), dict(edge_thickness=float("nan"))):
            with self.assertRaises(EngineValidationError, msg=bad):
                engine.calculate(dict(self.base, **bad))


class CutSizeTests(SimpleTestCase):
    def test_zero_tape_leaves_sizes_unchanged(self):
        p = engine.Part("x", 500, 700, 18, 1, "MDF", edge_w=2, edge_h=2)
        self.assertEqual(p.cut_size(0), (500, 700))

    def test_each_edge_closes_the_other_dimension(self):
        p = engine.Part("x", 500, 700, 18, 1, "MDF", edge_w=1, edge_h=0)  # one edge running along the 500 side
        self.assertEqual(p.cut_size(2), (500, 698))
        p = engine.Part("x", 500, 700, 18, 1, "MDF", edge_w=0, edge_h=2)
        self.assertEqual(p.cut_size(1), (498, 700))


class PricingTests(SimpleTestCase):
    cab = dict(width=800, height=2000, depth=400, thickness=18, shelves=3, doors=2)

    def calc(self, prices):
        return engine.calculate(self.cab, prices)["pricing"]

    def test_no_prices_no_pricing_block(self):
        self.assertNotIn("pricing", engine.calculate(self.cab))

    def test_hand_checked_amounts(self):
        # MDF 18 mm area: sides 1.6 + top/bottom 2*0.3056 + shelves 0.87096 + doors 1.582828 = 4.664988 -> 4.665 m2
        # HDF 4 mm: 0.796 * 1.996 = 1.588816 -> 1.5888 m2. Edge banding 17.39 m. Hinges 8 (2 doors x 4).
        pr = self.calc({"currency": "UZS", "waste_factor": 0, "edge_allowance": 0, "board_price_per_m2": {"MDF 18": 100, "HDF": 20},
                        "edge_price_per_m": 10, "hardware_prices": {"Hinge": 5}, "labor_per_m2": 2, "markup_pct": 10})
        lines = {(l["category"], l["item"]): l for l in pr["lines"]}
        self.assertAlmostEqual(lines[("board", "MDF 18 mm")]["amount"], 466.5, places=2)
        self.assertAlmostEqual(lines[("board", "HDF 4 mm")]["amount"], 31.78, places=2)
        self.assertAlmostEqual(lines[("edge_banding", "Edge banding tape")]["amount"], 173.9, places=2)
        self.assertEqual(lines[("hardware", "Hinge")]["amount"], 40)
        self.assertAlmostEqual(pr["subtotals"]["board"], 498.28, places=2)
        # every priced line is quantity x unit price; totals are the sums of the displayed amounts
        for l in pr["lines"]:
            if l["amount"] is not None:
                self.assertAlmostEqual(l["amount"], l["quantity"] * l["unit_price"], delta=0.006)
        self.assertAlmostEqual(pr["manufacturing_cost"], sum(l["amount"] for l in pr["lines"] if l["amount"] is not None), places=2)
        self.assertAlmostEqual(pr["markup_amount"], pr["manufacturing_cost"] * 0.10, delta=0.006)
        self.assertAlmostEqual(pr["total_price"], pr["manufacturing_cost"] + pr["markup_amount"], places=2)
        self.assertEqual(pr["currency"], "UZS")

    def test_missing_prices_are_reported_not_invented(self):
        pr = self.calc({"board_price_per_m2": {"MDF 18": 100}})
        self.assertFalse(pr["complete"])
        self.assertIn("board: HDF 4 mm", pr["missing"])
        self.assertIn("edge_banding: Edge banding tape", pr["missing"])
        self.assertIn("hardware: Hinge", pr["missing"])
        self.assertIn("labor: Manufacturing labour", pr["missing"])
        missing_line = next(l for l in pr["lines"] if l["item"] == "Hinge")
        self.assertIsNone(missing_line["unit_price"])
        self.assertIsNone(missing_line["amount"])
        self.assertEqual(pr["subtotals"]["hardware"], 0)

    def test_complete_when_everything_is_priced(self):
        names = {h["name"]: 1 for h in engine.calculate(self.cab)["hardware"]}
        pr = self.calc({"board_price_per_m2": {"MDF": 1, "HDF": 1}, "edge_price_per_m": 1, "hardware_prices": names, "labor_per_m2": 1})
        self.assertTrue(pr["complete"])
        self.assertEqual(pr["missing"], [])

    def test_zero_is_a_valid_price(self):
        pr = self.calc({"board_price_per_m2": {"MDF": 0, "HDF": 0}})
        self.assertNotIn("board: MDF 18 mm", pr["missing"])

    def test_thickness_specific_key_beats_material_key(self):
        pr = self.calc({"waste_factor": 0, "board_price_per_m2": {"MDF": 1, "mdf 18": 100}})
        mdf = next(l for l in pr["lines"] if l["item"] == "MDF 18 mm")
        self.assertEqual(mdf["unit_price"], 100)

    def test_waste_factor_is_applied_to_board_only(self):
        a = self.calc({"waste_factor": 0, "board_price_per_m2": {"MDF": 100}})
        b = self.calc({"waste_factor": 0.5, "board_price_per_m2": {"MDF": 100}})
        self.assertAlmostEqual(b["subtotals"]["board"], a["subtotals"]["board"] * 1.5, delta=0.02)

    def test_price_validation(self):
        for bad in ({"board_price_per_m2": {"MDF": -1}}, {"board_price_per_m2": {"MDF": True}}, {"board_price_per_m2": []},
                    {"hardware_prices": {"Hinge": "5"}}, {"waste_factor": 2}, {"markup_pct": -1}, {"edge_price_per_m": float("nan")},
                    {"currency": "far too long currency"}, {"surprise": 1}):
            with self.assertRaises(EngineValidationError, msg=bad):
                self.calc(bad)
        with self.assertRaises(EngineValidationError):
            engine.calculate(self.cab, "free")

    def test_prices_are_checked_before_the_cabinet(self):
        with self.assertRaises(EngineValidationError) as cm:
            engine.calculate(dict(self.cab, width=-1), {"markup_pct": -5})
        self.assertIn("prices.markup_pct", cm.exception.errors)
