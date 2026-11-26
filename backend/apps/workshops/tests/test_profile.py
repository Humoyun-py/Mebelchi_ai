from decimal import Decimal

from django.test import TestCase

from apps.core.tests.helpers import client_for, make_user
from apps.marketplace.tests.helpers import prices
from apps.workshops.models import Workshop
from apps.workshops.tests.helpers import WS, make_workshop


class ProfileTests(TestCase):
    def setUp(self):
        self.owner = make_user("o@x.com", "workshop")
        self.ws = make_workshop(self.owner)
        self.c = client_for(self.owner)
        self.url = f"{WS}{self.ws.pk}/"

    def patch(self, **body):
        return self.c.patch(self.url, body, format="json")

    def test_owner_sets_location_availability_capacity_and_prices(self):
        r = self.patch(latitude="41.311100", longitude="69.279700", delivery_radius_km=60, categories=["kitchen", "office"], working_hours="Mon-Sat 9-18",
                       max_active_orders=5, is_accepting_orders=False, lead_time_days=10, transport_per_km="0.50", assembly_percent="8", price_list=prices())
        self.assertEqual(r.status_code, 200, r.data)
        self.ws.refresh_from_db()
        self.assertEqual((self.ws.latitude, self.ws.delivery_radius_km, self.ws.categories, self.ws.is_accepting_orders, self.ws.assembly_percent),
                         (Decimal("41.311100"), 60, ["kitchen", "office"], False, Decimal("8.00")))
        self.assertEqual(r.data["price_list"]["markup_pct"], 20)

    def test_coordinates_are_validated_and_come_as_a_pair(self):
        self.assertEqual(self.patch(latitude="91", longitude="10").status_code, 400)
        self.assertEqual(self.patch(latitude="10", longitude="181").status_code, 400)
        self.assertEqual(self.patch(latitude="10").status_code, 400)
        self.assertEqual(self.patch(latitude="10", longitude="20").status_code, 200)
        self.assertEqual(self.patch(longitude=None).status_code, 400)

    def test_bad_values_are_refused(self):
        for body in ({"categories": ["spaceship"]}, {"categories": "kitchen"}, {"max_active_orders": 0}, {"lead_time_days": 0}, {"assembly_percent": "101"},
                     {"transport_per_km": "-1"}, {"price_list": {"board_price_per_m2": {"MDF": -3}}}, {"price_list": {"nonsense": 1}}, {"delivery_radius_km": -5}):
            self.assertEqual(self.patch(**body).status_code, 400, body)

    def test_rating_is_read_only(self):
        self.patch(rating_avg="5.00", rating_count=999)
        self.ws.refresh_from_db()
        self.assertEqual((self.ws.rating_avg, self.ws.rating_count), (0, 0))

    def test_only_the_owner_edits_the_profile(self):
        stranger = client_for(make_user("s@x.com", "workshop"))
        self.assertEqual(stranger.patch(self.url, {"latitude": "1", "longitude": "1"}, format="json").status_code, 404)

    def test_defaults_are_safe(self):
        w = Workshop.objects.get(pk=self.ws.pk)
        self.assertEqual((w.latitude, w.is_accepting_orders, w.max_active_orders, w.lead_time_days, w.price_list), (None, True, 10, 14, {}))
