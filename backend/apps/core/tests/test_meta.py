from django.test import TestCase
from rest_framework.test import APIClient

from apps.cutting_lists.optimizer import optimize


class MetaTests(TestCase):
    def test_meta_is_public_and_complete(self):
        d = APIClient().get("/api/v1/meta/").data
        self.assertEqual(d["limits"]["width"], [200, 4000])
        self.assertEqual({r["id"] for r in d["rooms"]}, {"kitchen", "bedroom", "living", "office"})
        self.assertEqual(len(d["content"]["faq"]), 4 + 1)
        self.assertEqual(len(d["showcase"]), 5)
        self.assertEqual([s["value"] for s in d["stats"]][0], len(d["furniture_categories"]))
        for item in d["content"]["features"]:
            self.assertEqual(set(item["title"]), {"en", "uz", "ru"})

    def test_optimizer_returns_colors_and_legend(self):
        r = optimize([dict(name="A", width=300, height=600, quantity=2), dict(name="B", width=200, height=400, quantity=1)], 2800, 2070)
        self.assertEqual({p["name"] for s in r["sheets"] for p in s["placements"] if p["color"]}, {"A", "B"})
        self.assertEqual({(l["name"], l["quantity"]) for l in r["legend"]}, {("A", 2), ("B", 1)})


class ThrottleDesignTests(TestCase):
    def test_signed_file_and_static_endpoints_are_not_ip_throttled(self):
        """Regression: gallery pages load many signed images at once; the anonymous per-IP limit returned 429s."""
        from apps.core.meta import MetaView
        from apps.files.views import FileDownloadView
        from apps.galleries.views import GalleryFileView
        from apps.subscriptions.views import PlanListView
        from apps.users.views import AvatarFileView
        for v in (MetaView, PlanListView, GalleryFileView, FileDownloadView, AvatarFileView):
            self.assertEqual(list(v.throttle_classes), [], v.__name__)

    def test_expensive_and_auth_endpoints_stay_throttled(self):
        from apps.accounts.views import LoginView, RegisterView
        from apps.geometry.views import PreviewView
        self.assertTrue(LoginView.throttle_classes and RegisterView.throttle_classes)
        self.assertTrue(PreviewView.throttle_classes)  # inherits the default anonymous throttle
