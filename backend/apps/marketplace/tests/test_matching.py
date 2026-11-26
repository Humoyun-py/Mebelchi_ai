from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from apps.core.tests.helpers import client_for
from apps.furniture.models import FurnitureTemplate
from apps.marketplace import geo, pricing
from apps.marketplace.tests.helpers import FURN, customer, prices, shop
from apps.workshops.models import Order, Workshop

MATCH = "/api/v1/marketplace/match/"
TASHKENT = {"latitude": 41.3111, "longitude": 69.2797}
SAMARKAND = {"latitude": 39.6542, "longitude": 66.9597}


class GeoAndPriceTests(SimpleTestCase):
    def test_haversine_known_distances(self):
        self.assertAlmostEqual(geo.haversine_km(41.3111, 69.2797, 39.6542, 66.9597), 265, delta=6)    # Tashkent - Samarkand by air
        self.assertEqual(geo.haversine_km(10, 10, 10, 10), 0)

    def test_tiers_are_real_quotes_only(self):
        t = [Decimal("100"), Decimal("150"), Decimal("200")]
        self.assertEqual(pricing.tiers(t), {"min": "100.00", "average": "150.00", "premium": "200.00", "quotes": 3})
        self.assertIsNone(pricing.tiers([]))
        self.assertEqual([pricing.tier_of(x, t) for x in t], ["min", "average", "premium"])
        self.assertEqual(pricing.tier_of(Decimal("5"), [Decimal("5")]), "average")


class MatchingTests(TestCase):
    def setUp(self):
        self.cheap = shop("Cheap", "c@x.com", scale=0.7, lead_time_days=20)
        self.mid = shop("Mid", "m@x.com", scale=1.0, lead_time_days=14)
        self.dear = shop("Dear", "d@x.com", scale=1.6, lead_time_days=7)
        self.user, self.c = customer()

    def match(self, **kw):
        r = self.c.post(MATCH, {"furniture": FURN, **kw}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        return r.data

    def test_returns_ranked_options_with_prices_tiers_and_explanations(self):
        d = self.match(customer_location=TASHKENT)
        self.assertEqual(len(d["options"]), 3, d["excluded"])
        o = d["options"][0]
        for k in ("workshop", "name", "price", "price_tier", "lead_time_days", "distance_km", "rating", "score", "score_parts", "quote", "portfolio", "flags"):
            self.assertIn(k, o)
        totals = sorted(Decimal(x["price"]) for x in d["options"])
        self.assertEqual((d["tiers"]["min"], d["tiers"]["premium"]), (f"{totals[0]:.2f}", f"{totals[-1]:.2f}"))
        self.assertEqual({x["price_tier"] for x in d["options"]}, {"min", "average", "premium"})
        self.assertTrue(all(d["options"][i]["score"] >= d["options"][i + 1]["score"] for i in range(2)))

    def test_matching_creates_nothing_and_contacts_nobody(self):
        from apps.notifications.models import Notification
        before = Notification.objects.count()
        self.match()
        self.assertEqual((Order.objects.count(), Notification.objects.count()), (0, before))

    def test_same_request_same_ranking(self):
        a, b = self.match(customer_location=TASHKENT), self.match(customer_location=TASHKENT)
        self.assertEqual([x["workshop"] for x in a["options"]], [x["workshop"] for x in b["options"]])

    def test_cheaper_workshop_wins_when_everything_else_is_equal(self):
        Workshop.objects.update(lead_time_days=14)
        d = self.match(customer_location=TASHKENT)
        self.assertEqual(d["options"][0]["workshop"], self.cheap.pk)

    def test_distance_beats_price_when_the_cheap_one_is_far(self):
        Workshop.objects.filter(pk=self.cheap.pk).update(latitude=Decimal("39.6542"), longitude=Decimal("66.9597"), lead_time_days=14, price_list=prices(0.97))
        Workshop.objects.filter(pk=self.mid.pk).update(lead_time_days=14)
        Workshop.objects.filter(pk=self.dear.pk).update(lead_time_days=14, price_list=prices(1.05))
        d = self.match(customer_location=TASHKENT)
        self.assertNotEqual(d["options"][0]["workshop"], self.cheap.pk, [(o["workshop"], o["price"], o["distance_km"], o["score_parts"]) for o in d["options"]])
        self.assertGreater(next(o for o in d["options"] if o["workshop"] == self.cheap.pk)["distance_km"], 200)

    def test_rating_counts(self):
        Workshop.objects.update(lead_time_days=14, price_list=prices(1.0))
        Workshop.objects.filter(pk=self.dear.pk).update(rating_avg=Decimal("5.00"), rating_count=20)
        Workshop.objects.filter(pk=self.mid.pk).update(rating_avg=Decimal("2.00"), rating_count=20)
        order = [o["workshop"] for o in self.match(customer_location=TASHKENT)["options"]]
        self.assertLess(order.index(self.dear.pk), order.index(self.mid.pk))

    def test_hard_filters_are_reported_with_reasons(self):
        Workshop.objects.filter(pk=self.cheap.pk).update(is_accepting_orders=False)
        Workshop.objects.filter(pk=self.mid.pk).update(categories=["bedroom"])
        Workshop.objects.filter(pk=self.dear.pk).update(price_list={})
        d = self.match()
        self.assertEqual(d["options"], [])
        self.assertEqual(d["tiers"], None)
        # a workshop that is not accepting orders is not even a candidate; the other two are reported
        reasons = {e["workshop"]: e["reason"] for e in d["excluded"]}
        self.assertIn("does not make", reasons[self.mid.pk])
        self.assertIn("price list", reasons[self.dear.pk])
        self.assertNotIn(self.cheap.pk, reasons)

    def test_delivery_radius_deadline_and_capacity(self):
        Workshop.objects.filter(pk=self.cheap.pk).update(delivery_radius_km=50, latitude=Decimal("39.6542"), longitude=Decimal("66.9597"))
        Workshop.objects.filter(pk=self.dear.pk).update(max_active_orders=1)
        Order.objects.create(workshop=self.dear, order_number="X-1", customer_name="a", title="t", status="in_production")
        d = self.match(customer_location=TASHKENT, deadline_days=10)
        reasons = {e["workshop"]: e["reason"] for e in d["excluded"]}
        self.assertIn("does not deliver that far", reasons[self.cheap.pk])
        self.assertIn("free capacity", reasons[self.dear.pk])
        self.assertIn("longer than the 10", reasons[self.mid.pk])

    def test_budget_flags_and_demotes_but_still_shows_prices(self):
        d = self.match(budget="1")
        self.assertTrue(all("over_budget" in o["flags"] for o in d["options"]))

    def test_unknown_distance_is_flagged_not_invented(self):
        d = self.match()
        self.assertTrue(all(o["distance_km"] is None and "distance_unknown" in o["flags"] for o in d["options"]))

    def test_incomplete_price_list_never_gets_a_made_up_price(self):
        pl = prices()
        pl["hardware_prices"].pop("Hinge")
        Workshop.objects.filter(pk=self.mid.pk).update(price_list=pl)
        d = self.match()
        self.assertNotIn(self.mid.pk, [o["workshop"] for o in d["options"]])
        self.assertIn("Hinge", next(e["reason"] for e in d["excluded"] if e["workshop"] == self.mid.pk))

    def test_transport_and_assembly_are_added_from_the_workshops_own_rates(self):
        base = Decimal(self.match(customer_location=TASHKENT)["options"][0]["price"])
        Workshop.objects.update(assembly_percent=Decimal("10"))
        with_assembly = Decimal(self.match(customer_location=TASHKENT)["options"][0]["price"])
        self.assertGreater(with_assembly, base)
        Workshop.objects.filter(pk=self.cheap.pk).update(transport_per_km=Decimal("1.00"), latitude=Decimal("39.6542"), longitude=Decimal("66.9597"))
        o = next(x for x in self.match(customer_location=TASHKENT, limit=10)["options"] if x["workshop"] == self.cheap.pk)
        self.assertTrue(any(l["category"] == "transport" for l in o["quote"]["lines"]))

    def test_catalog_item_with_a_fixed_price_is_used_by_its_own_workshop_only(self):
        item = FurnitureTemplate.objects.create(slug="fixed", category="kitchen", name="Fixed", defaults={**{k: v for k, v in FURN.items() if k != "category"}},
                                                workshop=self.mid, price=Decimal("123.45"), currency="USD", status="approved", lead_time_days=3)
        d = self.match(catalog_item=item.pk, furniture=None)
        mine = next(o for o in d["options"] if o["workshop"] == self.mid.pk)
        self.assertEqual((mine["price"], mine["quote"]["source"], mine["lead_time_days"]), ("123.45", "catalog", 3))
        self.assertTrue(any("another workshop" in e["reason"] for e in d["excluded"]) or len(d["options"]) == 1)

    def test_validation_errors(self):
        for body in ({}, {"furniture": {**FURN, "category": "spaceship"}}, {"furniture": {**FURN, "width": 1}}, {"furniture": FURN, "quantity": 0},
                     {"furniture": FURN, "customer_location": {"latitude": 999, "longitude": 0}}, {"furniture": FURN, "budget": -5},
                     {"furniture": FURN, "limit": 99}, {"catalog_item": 999999}, {"furniture": FURN, "deadline_days": "x"}):
            self.assertEqual(self.c.post(MATCH, body, format="json").status_code, 400, body)

    def test_login_required_and_exclude(self):
        from rest_framework.test import APIClient
        self.assertEqual(APIClient().post(MATCH, {}, format="json").status_code, 401)
        d = self.match(exclude_workshops=[self.cheap.pk, self.mid.pk])
        self.assertEqual([o["workshop"] for o in d["options"]], [self.dear.pk], d["excluded"])
