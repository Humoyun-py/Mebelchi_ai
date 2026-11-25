from decimal import Decimal

from django.test import TestCase

from apps.core.tests.helpers import CAB, client_for, make_user
from apps.materials.models import Material

CALC = "/api/v1/calculations/material/"
CL = "/api/v1/cutting-lists/"


class NewParametersApiTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.c = client_for(self.user)

    def test_old_payload_still_works_and_has_no_pricing(self):
        r = self.c.post(CALC, CAB, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertNotIn("pricing", r.data)
        self.assertEqual(r.data["input"]["cabinet_type"], "standard")

    def test_sliding_wardrobe_via_api(self):
        r = self.c.post(CALC, dict(width=1800, height=2300, depth=600, doors=3, shelves=2, cabinet_type="sliding_wardrobe", edge_thickness=0.8),
                        format="json")
        self.assertEqual(r.status_code, 200, r.data)
        door = next(p for p in r.data["parts"] if p["name"] == "Sliding door")
        self.assertEqual((door["width"], door["height"], door["cut_width"]), (608, 2209, 606.4))

    def test_kitchen_types_via_api(self):
        for t, depth in (("kitchen_base", 560), ("kitchen_wall", 320)):
            r = self.c.post(CALC, dict(width=600, height=720, depth=depth, doors=1, cabinet_type=t), format="json")
            self.assertEqual(r.status_code, 200, (t, r.data))

    def test_validation_errors_are_field_errors(self):
        r = self.c.post(CALC, dict(CAB, cabinet_type="nope"), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("cabinet_type", r.data["error"]["fields"])
        r = self.c.post(CALC, dict(CAB, cabinet_type="sliding_wardrobe", doors=1), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("doors", r.data["error"]["fields"])
        r = self.c.post(CALC, dict(CAB, edge_thickness=9), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("edge_thickness", r.data["error"]["fields"])

    def test_requires_authentication(self):
        self.assertEqual(client_for().post(CALC, CAB, format="json").status_code, 401)

    def test_saved_calculation_keeps_pricing_and_new_inputs(self):
        r = self.c.post(CALC, dict(CAB, save=True, name="Priced", prices={"board_price_per_m2": {"MDF": 10}}), format="json")
        saved = self.c.get(f"/api/v1/calculations/{r.data['saved_id']}/").data
        self.assertIn("pricing", saved["result"])
        self.assertEqual(saved["inputs"]["cabinet_type"], "standard")


class PricingApiTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.c = client_for(self.user)

    def test_explicit_prices(self):
        r = self.c.post(CALC, dict(CAB, prices={"currency": "UZS", "board_price_per_m2": {"MDF": 100, "HDF": 20}, "waste_factor": 0}), format="json")
        self.assertEqual(r.status_code, 200, r.data)
        pr = r.data["pricing"]
        self.assertFalse(pr["complete"])
        self.assertAlmostEqual(pr["subtotals"]["board"], 498.28, places=2)

    def test_invalid_prices_are_rejected(self):
        r = self.c.post(CALC, dict(CAB, prices={"board_price_per_m2": {"MDF": -5}}), format="json")
        self.assertEqual(r.status_code, 400)
        r = self.c.post(CALC, dict(CAB, prices={"markup_pct": 999}), format="json")
        self.assertEqual(r.status_code, 400)

    def test_catalog_prices_use_the_users_sheet_price(self):
        # 2800 x 2070 mm = 5.796 m2; 579 600 per sheet -> 100 000 per m2
        Material.objects.create(owner=self.user, name="My MDF", kind="MDF", thickness=Decimal("18"), sheet_length=2800, sheet_width=2070,
                                price_per_sheet=Decimal("579600"))
        r = self.c.post(CALC, dict(CAB, use_catalog_prices=True), format="json")
        self.assertEqual(r.status_code, 200, r.data)
        mdf = next(l for l in r.data["pricing"]["lines"] if l["item"] == "MDF 18 mm")
        self.assertEqual(mdf["unit_price"], 100000)
        hdf = next(l for l in r.data["pricing"]["lines"] if l["item"] == "HDF 4 mm")
        self.assertIsNone(hdf["unit_price"])  # no sheet price known: reported as missing, not guessed

    def test_explicit_price_wins_over_catalog(self):
        Material.objects.create(owner=self.user, name="My MDF", kind="MDF", thickness=Decimal("18"), price_per_sheet=Decimal("579600"))
        r = self.c.post(CALC, dict(CAB, use_catalog_prices=True, prices={"board_price_per_m2": {"MDF 18": 7}}), format="json")
        mdf = next(l for l in r.data["pricing"]["lines"] if l["item"] == "MDF 18 mm")
        self.assertEqual(mdf["unit_price"], 7)

    def test_other_users_materials_are_never_used(self):
        other = make_user("other@x.com")
        Material.objects.create(owner=other, name="Secret price", kind="MDF", thickness=Decimal("18"), price_per_sheet=Decimal("1000"))
        r = self.c.post(CALC, dict(CAB, use_catalog_prices=True), format="json")
        mdf = next(l for l in r.data["pricing"]["lines"] if l["item"] == "MDF 18 mm")
        self.assertIsNone(mdf["unit_price"])

    def test_no_pricing_without_request(self):
        Material.objects.create(owner=self.user, name="My MDF", kind="MDF", thickness=Decimal("18"), price_per_sheet=Decimal("579600"))
        self.assertNotIn("pricing", self.c.post(CALC, CAB, format="json").data)


class CuttingListEdgeTests(TestCase):
    def setUp(self):
        self.c = client_for(make_user())

    def test_cut_sizes_are_stored_when_tape_is_set(self):
        r = self.c.post(CL + "from-calculation/", dict(CAB, name="Banded", edge_thickness=0.8), format="json")
        self.assertEqual(r.status_code, 201, r.data)
        door = next(p for p in r.data["parts"] if p["name"] == "Door")
        self.assertEqual((float(door["width"]), float(door["height"])), (394.9, 1994.4))  # 396.5 - 1.6 ; 1996 - 1.6
        self.assertIn("0.8 mm tape deducted", door["edge_note"])
        o = self.c.post(f"{CL}{r.data['id']}/optimize/", {}, format="json")
        self.assertEqual(o.status_code, 201, o.data)
        self.assertEqual(o.data["result"]["summary"]["unplaced_count"], 0)

    def test_without_tape_nothing_changes(self):
        r = self.c.post(CL + "from-calculation/", dict(CAB), format="json")
        door = next(p for p in r.data["parts"] if p["name"] == "Door")
        self.assertEqual(float(door["width"]), 396.5)
        self.assertNotIn("tape", door["edge_note"])

    def test_sliding_cutting_list(self):
        r = self.c.post(CL + "from-calculation/", dict(width=1800, height=2300, depth=600, doors=3, cabinet_type="sliding_wardrobe"), format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIn("Sliding door", [p["name"] for p in r.data["parts"]])

    def test_optimization_result_is_flagged_approximate_and_valid(self):
        r = self.c.post(CL + "from-calculation/", dict(CAB), format="json")
        res = self.c.post(f"{CL}{r.data['id']}/optimize/", {}, format="json").data["result"]
        self.assertTrue(res["approximate"])
        self.assertFalse(res["is_optimal"])
        self.assertTrue(res["validation"]["valid"])
        self.assertTrue(all(g["result"]["validation"]["valid"] for g in res["groups"]))


class CatalogKeyTests(TestCase):
    def test_decimal_thickness_from_the_database_matches_the_price_key(self):
        """A DecimalField read back from the database is Decimal('18.0'); the key must still be 'MDF 18'."""
        from apps.calculations.pricing import catalog_board_prices
        u = make_user()
        Material.objects.create(owner=u, name="m", kind="MDF", thickness=Decimal("18"), price_per_sheet=Decimal("579600"))
        Material.objects.create(owner=u, name="h", kind="HDF", thickness=Decimal("3.5"), sheet_length=2440, sheet_width=1830, price_per_sheet=Decimal("446520"))
        prices = catalog_board_prices(u)
        self.assertEqual(prices["MDF 18"], 100000.0)
        self.assertEqual(prices["HDF 3.5"], 100000.0)  # 446 520 / (2.44 x 1.83 = 4.4652 m2)
