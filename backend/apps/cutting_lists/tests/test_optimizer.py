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
