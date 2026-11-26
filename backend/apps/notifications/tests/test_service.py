from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.tests.helpers import client_for, make_user
from apps.notifications.models import Notification
from apps.notifications.services import notify

URL = "/api/v1/notifications/"


class NotificationAccessTests(TestCase):
    def setUp(self):
        self.a, self.b = make_user("a@x.com"), make_user("b@x.com")
        self.n = Notification.objects.create(user=self.a, title="Mine")

    def test_login_is_required_on_every_route(self):
        anon = APIClient()
        for call in (anon.get(URL), anon.get(f"{URL}{self.n.pk}/"), anon.post(f"{URL}{self.n.pk}/read/"), anon.post(f"{URL}read-all/"), anon.get(f"{URL}unread-count/"), anon.delete(f"{URL}{self.n.pk}/")):
            self.assertEqual(call.status_code, 401)

    def test_a_stranger_cannot_read_mark_or_delete(self):
        cb = client_for(self.b)
        self.assertEqual(cb.get(f"{URL}{self.n.pk}/").status_code, 404)
        self.assertEqual(cb.post(f"{URL}{self.n.pk}/read/").status_code, 404)
        self.assertEqual(cb.delete(f"{URL}{self.n.pk}/").status_code, 404)
        self.assertEqual(cb.post(f"{URL}read-all/").data["updated"], 0)
        self.assertFalse(Notification.objects.get(pk=self.n.pk).read)

    def test_read_all_touches_only_my_rows_and_notifications_cannot_be_created_through_the_api(self):
        Notification.objects.create(user=self.b, title="Theirs")
        self.assertEqual(client_for(self.a).post(f"{URL}read-all/").data["updated"], 1)
        self.assertFalse(Notification.objects.get(user=self.b).read)
        self.assertEqual(client_for(self.a).post(URL, {"title": "x"}, format="json").status_code, 405)


class NotifyServiceTests(TestCase):
    def test_the_in_app_row_is_created_and_a_telegram_push_is_queued_after_commit(self):
        u = make_user("a@x.com")
        with mock.patch("apps.integrations.tasks.notify_user_on_telegram.delay") as push, self.captureOnCommitCallbacks(execute=True):
            n = notify(u, "Hello", "body", "success")
        self.assertEqual((n.title, n.body, n.level, n.read), ("Hello", "body", "success", False))
        push.assert_called_once_with(u.id, "Hello", "body")

    def test_a_user_who_turned_system_notifications_off_gets_nothing(self):
        u = make_user("a@x.com"); u.notify_system = False; u.save()
        with mock.patch("apps.integrations.tasks.notify_user_on_telegram.delay") as push, self.captureOnCommitCallbacks(execute=True):
            self.assertIsNone(notify(u, "Hello"))
        self.assertEqual(Notification.objects.count(), 0)
        push.assert_not_called()

    def test_a_broker_outage_never_breaks_the_caller_and_keeps_the_notification(self):
        u = make_user("a@x.com")
        with mock.patch("apps.integrations.tasks.notify_user_on_telegram.delay", side_effect=ConnectionError("redis down")), \
             self.assertLogs("mebelchi.notifications", "ERROR"), self.captureOnCommitCallbacks(execute=True):   # callbacks run when the inner block exits
            n = notify(u, "Hello")
        self.assertTrue(Notification.objects.filter(pk=n.pk).exists())

    def test_nothing_is_pushed_when_the_surrounding_transaction_rolls_back(self):
        u = make_user("a@x.com")
        from django.db import transaction
        with mock.patch("apps.integrations.tasks.notify_user_on_telegram.delay") as push, self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    notify(u, "Hello")
                    raise RuntimeError("boom")
            except RuntimeError:
                pass
        self.assertEqual(Notification.objects.count(), 0)
        push.assert_not_called()
