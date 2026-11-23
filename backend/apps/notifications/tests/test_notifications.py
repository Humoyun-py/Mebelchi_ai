from django.test import TestCase

from apps.core.tests.helpers import client_for, make_user
from apps.notifications.models import Notification


class NotificationTests(TestCase):
    def setUp(self):
        self.a, self.b = make_user("a@example.com"), make_user("b@example.com")
        self.ca, self.cb = client_for(self.a), client_for(self.b)
        self.n1 = Notification.objects.create(user=self.a, title="One")
        self.n2 = Notification.objects.create(user=self.a, title="Two")
        self.nb = Notification.objects.create(user=self.b, title="Other")

    def test_list_only_own_and_unread_count(self):
        self.assertEqual(self.ca.get("/api/v1/notifications/").data["count"], 2)
        self.assertEqual(self.ca.get("/api/v1/notifications/unread-count/").data["count"], 2)

    def test_mark_read_and_read_all(self):
        self.assertTrue(self.ca.post(f"/api/v1/notifications/{self.n1.id}/read/").data["read"])
        self.assertEqual(self.ca.get("/api/v1/notifications/unread-count/").data["count"], 1)
        self.assertEqual(self.ca.post("/api/v1/notifications/read-all/").data["updated"], 1)
        self.assertEqual(self.ca.get("/api/v1/notifications/unread-count/").data["count"], 0)
        self.assertFalse(Notification.objects.get(pk=self.nb.pk).read)

    def test_cannot_touch_foreign_notification(self):
        self.assertEqual(self.ca.post(f"/api/v1/notifications/{self.nb.id}/read/").status_code, 404)
        self.assertEqual(self.ca.delete(f"/api/v1/notifications/{self.nb.id}/").status_code, 404)
        self.assertEqual(self.ca.delete(f"/api/v1/notifications/{self.n1.id}/").status_code, 204)

    def test_read_only_fields(self):
        self.assertEqual(self.ca.patch(f"/api/v1/notifications/{self.n1.id}/", {"read": True}, format="json").status_code, 405)
