from django.test import TestCase

from apps.core.tests.helpers import client_for, make_user
from apps.subscriptions import services
from apps.subscriptions.models import Payment, Plan, Subscription


class SubscriptionTests(TestCase):
    def setUp(self):
        self.u = make_user("s@example.com")
        self.c = client_for(self.u)

    def test_plans_are_public_and_seeded(self):
        r = client_for().get("/api/v1/subscriptions/plans/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual([p["slug"] for p in r.data], ["free", "starter", "professional", "enterprise"])

    def test_new_user_is_on_free_plan(self):
        r = self.c.get("/api/v1/subscriptions/me/")
        self.assertEqual(r.data["plan"]["slug"], "free")
        self.assertEqual(r.data["projects"]["limit"], 5)

    def test_paid_upgrade_creates_pending_payment_only(self):
        r = self.c.post("/api/v1/subscriptions/upgrade/", {"plan": "starter"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["activated"])
        self.assertEqual(Payment.objects.get(user=self.u).status, "pending")
        self.assertEqual(self.c.get("/api/v1/subscriptions/me/").data["plan"]["slug"], "free")

    def test_confirm_payment_activates_plan(self):
        self.c.post("/api/v1/subscriptions/upgrade/", {"plan": "starter"}, format="json")
        services.confirm_payment(Payment.objects.get(user=self.u))
        fresh = client_for(type(self.u).objects.get(pk=self.u.pk))  # each real request loads the user anew
        self.assertEqual(fresh.get("/api/v1/subscriptions/me/").data["plan"]["slug"], "starter")
        self.assertEqual(Payment.objects.get(user=self.u).status, "paid")

    def test_unknown_or_inactive_plan_404(self):
        self.assertEqual(self.c.post("/api/v1/subscriptions/upgrade/", {"plan": "nope"}, format="json").status_code, 404)
        Plan.objects.filter(slug="starter").update(is_active=False)
        self.assertEqual(self.c.post("/api/v1/subscriptions/upgrade/", {"plan": "starter"}, format="json").status_code, 404)

    def test_requires_auth(self):
        self.assertEqual(client_for().get("/api/v1/subscriptions/me/").status_code, 401)
        self.assertEqual(client_for().post("/api/v1/subscriptions/upgrade/", {"plan": "starter"}, format="json").status_code, 401)

    def test_project_limit_enforced_on_free_plan(self):
        for i in range(5):
            self.assertEqual(self.c.post("/api/v1/projects/", {"name": f"P{i}"}, format="json").status_code, 201)
        self.assertEqual(self.c.post("/api/v1/projects/", {"name": "P6"}, format="json").status_code, 403)

    def test_unlimited_plan_has_no_project_limit(self):
        sub = services.ensure_subscription(self.u)
        sub.plan = Plan.objects.get(slug="professional")
        sub.save()
        for i in range(7):
            self.assertEqual(self.c.post("/api/v1/projects/", {"name": f"P{i}"}, format="json").status_code, 201)

    def test_storage_limit(self):
        from rest_framework.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied):
            services.enforce_storage_limit(self.u, 201 * 1024 * 1024)
        services.enforce_storage_limit(self.u, 1024)
        self.assertEqual(Subscription.objects.filter(user=self.u).count(), 1)
