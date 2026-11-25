from django.test import SimpleTestCase

from apps.cutting_lists.optimizer import OptimizerError, optimize


def overlaps(a, b):
    return not (a["x"] + a["w"] <= b["x"] + 1e-6 or b["x"] + b["w"] <= a["x"] + 1e-6 or a["y"] + a["h"] <= b["y"] + 1e-6 or b["y"] + b["h"] <= a["y"] + 1e-6)


class OptimizerTests(SimpleTestCase):
    parts = [dict(name="Side", width=400, height=2000, quantity=2), dict(name="Shelf", width=380, height=764, quantity=6, can_rotate=True),
             dict(name="Door", width=396, height=1996, quantity=2)]

    def test_no_overlap_and_inside_sheet(self):
        r = optimize(self.parts, 2800, 2070, kerf=3, trim=10)
        for s in r["sheets"]:
            for i, a in enumerate(s["placements"]):
                self.assertGreaterEqual(a["x"], 0)
                self.assertLessEqual(a["x"] + a["w"], 2800 - 20 + 1e-6)
                self.assertLessEqual(a["y"] + a["h"], 2070 - 20 + 1e-6)
                for b in s["placements"][i + 1:]:
                    self.assertFalse(overlaps(a, b), (a, b))

    def test_all_pieces_placed(self):
        r = optimize(self.parts, 2800, 2070)
        self.assertEqual(sum(len(s["placements"]) for s in r["sheets"]), 10)
        self.assertEqual(r["unplaced"], [])

    def test_area_accounting(self):
        r = optimize(self.parts, 2800, 2070)
        s = r["summary"]
        expected = sum(p["width"] * p["height"] * p["quantity"] for p in self.parts) / 1e6
        self.assertAlmostEqual(s["parts_area_m2"], expected, places=2)
        self.assertAlmostEqual(s["utilization_pct"] + s["waste_pct"], 100, places=1)

    def test_rotation_off_respected(self):
        r = optimize([dict(name="Tall", width=300, height=1000, quantity=3)], 2800, 2070)
        self.assertTrue(all(not p["rotated"] for s in r["sheets"] for p in s["placements"]))

    def test_oversized_reported_not_dropped(self):
        r = optimize([dict(name="Huge", width=3000, height=3000, quantity=2), dict(name="Ok", width=100, height=100, quantity=1)], 2800, 2070)
        self.assertEqual(len(r["unplaced"]), 2)
        self.assertEqual(r["summary"]["pieces_placed"], 1)

    def test_non_rotatable_needs_fit_in_orientation(self):
        # 2300 along-grain fits 2780 length; 2300 wide would not fit 2050 width -> only orientation used is valid
        r = optimize([dict(name="Long", width=2200, height=500, quantity=1)], 2800, 2070)
        self.assertEqual(len(r["unplaced"]), 1)  # width 2200 > usable 2050 and rotation not allowed

    def test_validation(self):
        with self.assertRaises(OptimizerError):
            optimize([dict(name="x", width=-1, height=10, quantity=1)], 2800, 2070)
        with self.assertRaises(OptimizerError):
            optimize(self.parts, 10, 2070)
        with self.assertRaises(OptimizerError):
            optimize([dict(name="x", width="a", height=10, quantity=1)], 2800, 2070)

    def test_deterministic(self):
        a, b = optimize(self.parts, 2800, 2070), optimize(self.parts, 2800, 2070)
        self.assertEqual(a["sheets"], b["sheets"])


class ExtraTrialTests(SimpleTestCase):
    mixed = [dict(name="A", width=530, height=1130, quantity=7, can_rotate=True), dict(name="B", width=310, height=870, quantity=11, can_rotate=True),
             dict(name="C", width=640, height=720, quantity=9), dict(name="D", width=220, height=1490, quantity=8, can_rotate=True),
             dict(name="E", width=450, height=980, quantity=6)]

    def test_random_trials_never_worse(self):
        base = optimize(self.mixed, 2800, 2070, trials=0)["summary"]
        better = optimize(self.mixed, 2800, 2070)["summary"]
        self.assertLessEqual(better["sheet_count"], base["sheet_count"])
        if better["sheet_count"] == base["sheet_count"]:
            self.assertGreaterEqual(better["last_sheet_offcut"]["width"], base["last_sheet_offcut"]["width"] - 1e-6)

    def test_trials_deterministic_and_valid(self):
        a, b = optimize(self.mixed, 2800, 2070), optimize(self.mixed, 2800, 2070)
        self.assertEqual(a["sheets"], b["sheets"])
        self.assertEqual(sum(len(s["placements"]) for s in a["sheets"]), 41)
        for s in a["sheets"]:
            for i, p in enumerate(s["placements"]):
                self.assertLessEqual(p["x"] + p["w"], 2780 + 1e-6)
                self.assertLessEqual(p["y"] + p["h"], 2050 + 1e-6)
                for q in s["placements"][i + 1:]:
                    self.assertFalse(overlaps(p, q))

    def test_large_job_stays_fast(self):
        import time
        big = [dict(name="X", width=300 + (i % 7) * 40, height=500 + (i % 5) * 90, quantity=40, can_rotate=True) for i in range(12)]
        t = time.time(); r = optimize(big, 2800, 2070); self.assertLess(time.time() - t, 5)
        self.assertEqual(sum(len(s["placements"]) for s in r["sheets"]), 480)


# ------------------------------------------------------------------ Phase 2: independent layout verification
import random
from unittest import mock

from apps.cutting_lists import optimizer as opt


def pl(pid, x, y, w, h, name="p"):
    return {"part_id": pid, "name": name, "x": x, "y": y, "w": w, "h": h, "rotated": False}


class LayoutCheckTests(SimpleTestCase):
    W, H = 1000, 500

    def check(self, *placements, kerf=3):
        return opt.check_placements(list(placements), self.W, self.H, kerf)

    def test_valid_layout_has_no_problems(self):
        self.assertEqual(self.check(pl(1, 0, 0, 400, 200), pl(2, 403, 0, 400, 200), pl(3, 0, 203, 400, 200)), [])

    def test_overlap_is_detected(self):
        problems = self.check(pl(1, 0, 0, 400, 200), pl(2, 300, 100, 400, 200))
        self.assertTrue(any("overlap" in p for p in problems), problems)

    def test_kerf_clearance_is_enforced_in_both_directions(self):
        self.assertTrue(any("kerf" in p for p in self.check(pl(1, 0, 0, 400, 200), pl(2, 401, 0, 100, 100))))      # 1 mm gap in x
        self.assertTrue(any("kerf" in p for p in self.check(pl(1, 0, 0, 400, 200), pl(2, 0, 201, 100, 100))))      # 1 mm gap in y
        self.assertEqual(self.check(pl(1, 0, 0, 400, 200), pl(2, 400, 0, 100, 100), kerf=0), [])                    # touching is fine without kerf

    def test_outside_the_sheet_is_detected(self):
        for bad in (pl(1, -5, 0, 100, 100), pl(1, 0, -5, 100, 100), pl(1, 950, 0, 100, 100), pl(1, 0, 450, 100, 100)):
            self.assertTrue(any("outside" in p for p in self.check(bad)), bad)

    def test_exactly_on_the_edge_is_inside(self):
        self.assertEqual(self.check(pl(1, 600, 300, 400, 200)), [])

    def test_zero_size_is_rejected(self):
        self.assertTrue(self.check(pl(1, 0, 0, 0, 100)))

    def test_order_of_placements_does_not_matter(self):
        a, b = pl(1, 0, 0, 400, 200), pl(2, 100, 50, 400, 200)
        self.assertEqual(len(self.check(a, b)), len(self.check(b, a)))

    def test_verify_result_catches_a_tampered_result(self):
        r = optimize(OptimizerTests.parts, 2800, 2070)
        self.assertEqual(opt.verify_result(r), [])
        r["sheets"][0]["placements"][1].update(x=r["sheets"][0]["placements"][0]["x"], y=r["sheets"][0]["placements"][0]["y"])
        self.assertTrue(opt.verify_result(r))


class OptimizerGuaranteeTests(SimpleTestCase):
    def test_result_declares_itself_approximate_and_valid(self):
        r = optimize(OptimizerTests.parts, 2800, 2070)
        self.assertTrue(r["approximate"])
        self.assertFalse(r["is_optimal"])
        self.assertIn("not a provably optimal", r["approximation_note"])
        self.assertTrue(r["validation"]["valid"])
        self.assertEqual(r["validation"]["pieces_checked"], 10)
        self.assertEqual(r["sheet"]["usable_area"], {"length": 2780, "width": 2050, "offset_x": 10, "offset_y": 10})

    def test_random_jobs_are_always_valid(self):
        rng = random.Random(20261125)
        for _ in range(120):
            parts = [dict(name=f"P{i}", width=rng.randint(40, 1200), height=rng.randint(40, 2600), quantity=rng.randint(1, 6),
                          can_rotate=rng.random() < 0.5) for i in range(rng.randint(1, 8))]
            kerf, trim = rng.choice([0, 2, 3, 4.5]), rng.choice([0, 5, 10, 20])
            r = optimize(parts, 2800, 2070, kerf=kerf, trim=trim, allow_rotation=rng.random() < 0.8)
            self.assertEqual(opt.verify_result(r), [], (parts, kerf, trim))
            placed = sum(len(s["placements"]) for s in r["sheets"])
            self.assertEqual(placed + len(r["unplaced"]), sum(p["quantity"] for p in parts))

    def test_rotation_never_happens_unless_allowed(self):
        rng = random.Random(7)
        for _ in range(40):
            parts = [dict(name=f"P{i}", width=rng.randint(100, 900), height=rng.randint(100, 1900), quantity=rng.randint(1, 4)) for i in range(5)]
            r = optimize(parts, 2800, 2070)
            self.assertTrue(all(not p["rotated"] for s in r["sheets"] for p in s["placements"]))

    def test_a_broken_packer_cannot_return_an_invalid_layout(self):
        def broken(items, W, H, kerf, mode):
            s = opt.Sheet()
            for it in items:  # every piece on top of each other
                s.placements.append({"part_id": it.uid, "name": it.name, "x": 0, "y": 0, "w": it.along, "h": it.across, "rotated": False})
            return [s]
        with mock.patch.object(opt, "_pack", broken):
            with self.assertRaises(OptimizerError) as cm:
                optimize([dict(name="A", width=300, height=600, quantity=2)], 2800, 2070)
        self.assertIn("layout check failed", str(cm.exception))

    def test_a_packer_that_loses_a_piece_is_caught(self):
        real = opt._pack

        def lossy(items, W, H, kerf, mode):
            return real(items[:-1], W, H, kerf, mode)
        with mock.patch.object(opt, "_pack", lossy):
            with self.assertRaises(OptimizerError) as cm:
                optimize([dict(name="A", width=300, height=600, quantity=3)], 2800, 2070)
        self.assertIn("not placed", str(cm.exception))

    def test_a_rotated_piece_that_may_not_rotate_is_caught(self):
        def rotating(items, W, H, kerf, mode):
            s = opt.Sheet()
            for it in items:
                s.placements.append({"part_id": it.uid, "name": it.name, "x": 0, "y": 0, "w": it.across, "h": it.along, "rotated": True})
            return [s]
        with mock.patch.object(opt, "_pack", rotating):
            with self.assertRaises(OptimizerError) as cm:
                optimize([dict(name="A", width=300, height=600, quantity=1)], 2800, 2070)
        self.assertIn("rotation is not allowed", str(cm.exception))
