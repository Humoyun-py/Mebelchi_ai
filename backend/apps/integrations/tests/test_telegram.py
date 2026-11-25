from datetime import timedelta
from unittest import mock

import httpx

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.tests.helpers import client_for, make_user
from apps.cutting_lists.models import CuttingList
from apps.integrations import services
from apps.integrations.models import LinkCode, TelegramLink
from apps.integrations.tasks import notify_user_on_telegram
from apps.notifications.models import Notification
from apps.projects.models import Project

SECRET = "test-bot-secret-value"


def err(response):
    """Error code from the project's error envelope: {"error": {"status", "detail", "fields": {"code": ...}}}."""
    return response.data["error"]["fields"]["code"]
BOT = {"HTTP_X_BOT_SECRET": SECRET}
CAB = {"width": 800, "height": 2000, "depth": 400, "thickness": 18, "shelves": 3, "doors": 2, "drawers": 0}


def bot_client():
    return APIClient()


@override_settings(TELEGRAM_BOT_API_SECRET=SECRET)
class LinkingFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_user("maker@x.com", role="maker")
        self.web = client_for(self.user)
        self.bot = bot_client()

    def issue_code(self):
        r = self.web.post("/api/v1/telegram/link-code/")
        self.assertEqual(r.status_code, 201)
        return r.data["code"]

    def test_code_format_and_status_before_linking(self):
        code = self.issue_code()
        self.assertRegex(code, r"^[A-Z2-9]{4}-[A-Z2-9]{4}$")
        self.assertFalse(self.web.get("/api/v1/telegram/status/").data["linked"])

    def test_new_code_invalidates_previous(self):
        first = self.issue_code()
        second = self.issue_code()
        self.assertNotEqual(first, second)
        r = self.bot.post("/api/v1/telegram/bot/link/", {"telegram_id": 111, "username": "u", "code": first}, format="json", **BOT)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(err(r), "invalid_code")

    def test_successful_link_accepts_lowercase_and_spaces_and_is_single_use(self):
        code = self.issue_code()
        messy = " " + code.lower().replace("-", " ") + " "
        r = self.bot.post("/api/v1/telegram/bot/link/", {"telegram_id": 555, "username": "maker", "code": messy}, format="json", **BOT)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["user"]["email"], "maker@x.com")
        self.assertEqual(TelegramLink.objects.get(user=self.user).telegram_id, 555)
        again = self.bot.post("/api/v1/telegram/bot/link/", {"telegram_id": 555, "username": "maker", "code": code}, format="json", **BOT)
        self.assertEqual(err(again), "invalid_code")
        status_data = self.web.get("/api/v1/telegram/status/").data
        self.assertTrue(status_data["linked"])
        self.assertEqual(status_data["username"], "maker")

    def test_linking_creates_an_in_app_notification(self):
        code = self.issue_code()
        self.bot.post("/api/v1/telegram/bot/link/", {"telegram_id": 556, "username": "", "code": code}, format="json", **BOT)
        self.assertTrue(Notification.objects.filter(user=self.user, title="Telegram account linked").exists())

    def test_expired_code_is_rejected(self):
        code = self.issue_code()
        LinkCode.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        r = self.bot.post("/api/v1/telegram/bot/link/", {"telegram_id": 557, "code": code}, format="json", **BOT)
        self.assertEqual(err(r), "expired")
        self.assertFalse(TelegramLink.objects.exists())

    def test_telegram_id_cannot_be_linked_to_two_accounts(self):
        other = make_user("other@x.com")
        TelegramLink.objects.create(user=other, telegram_id=900)
        code = self.issue_code()
        r = self.bot.post("/api/v1/telegram/bot/link/", {"telegram_id": 900, "code": code}, format="json", **BOT)
        self.assertEqual(err(r), "telegram_in_use")

    def test_brute_force_is_blocked_after_five_failures(self):
        self.issue_code()
        for _ in range(5):
            self.bot.post("/api/v1/telegram/bot/link/", {"telegram_id": 600, "code": "AAAA-AAAA"}, format="json", **BOT)
        real = self.issue_code()
        r = self.bot.post("/api/v1/telegram/bot/link/", {"telegram_id": 600, "code": real}, format="json", **BOT)
        self.assertEqual(err(r), "too_many_attempts")
        r2 = self.bot.post("/api/v1/telegram/bot/link/", {"telegram_id": 601, "code": real}, format="json", **BOT)
        self.assertEqual(r2.status_code, 200)  # the limit is per Telegram ID

    def test_unlink_from_web(self):
        code = self.issue_code()
        self.bot.post("/api/v1/telegram/bot/link/", {"telegram_id": 700, "code": code}, format="json", **BOT)
        self.assertEqual(self.web.delete("/api/v1/telegram/status/").status_code, 204)
        self.assertFalse(TelegramLink.objects.exists())

    def test_code_endpoint_requires_login(self):
        self.assertEqual(bot_client().post("/api/v1/telegram/link-code/").status_code, 401)


@override_settings(TELEGRAM_BOT_API_SECRET=SECRET)
class BotAuthenticationTests(TestCase):
    def test_missing_or_wrong_secret_is_forbidden(self):
        c = bot_client()
        self.assertEqual(c.get("/api/v1/telegram/bot/me/?telegram_id=1").status_code, 403)
        self.assertEqual(c.get("/api/v1/telegram/bot/me/?telegram_id=1", HTTP_X_BOT_SECRET="wrong").status_code, 403)

    @override_settings(TELEGRAM_BOT_API_SECRET="")
    def test_empty_secret_disables_bot_endpoints(self):
        self.assertEqual(bot_client().get("/api/v1/telegram/bot/me/?telegram_id=1", HTTP_X_BOT_SECRET="").status_code, 403)

    def test_unlinked_telegram_id_gets_not_linked(self):
        r = bot_client().get("/api/v1/telegram/bot/me/?telegram_id=1", **BOT)
        self.assertEqual(r.status_code, 404)
        self.assertEqual(err(r), "not_linked")

    def test_bot_requests_are_not_limited_by_per_ip_anonymous_throttle(self):
        c = bot_client()
        codes = [c.get("/api/v1/telegram/bot/me/?telegram_id=9", **BOT).status_code for _ in range(70)]
        self.assertNotIn(429, codes)


@override_settings(TELEGRAM_BOT_API_SECRET=SECRET)
class BotFeatureTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_user("maker@x.com")
        self.other = make_user("other@x.com")
        self.admin = make_user("admin@x.com", is_staff=True, is_superuser=True)
        TelegramLink.objects.create(user=self.user, telegram_id=1001, username="maker")
        TelegramLink.objects.create(user=self.admin, telegram_id=1002, username="admin")
        self.bot = bot_client()

    def get(self, url, tid=1001):
        return self.bot.get(f"{url}{'&' if '?' in url else '?'}telegram_id={tid}", **BOT)

    def test_me_returns_profile_and_unread_count(self):
        Notification.objects.create(user=self.user, title="x")
        r = self.get("/api/v1/telegram/bot/me/")
        self.assertEqual(r.data["user"]["email"], "maker@x.com")
        self.assertEqual(r.data["unread_notifications"], 1)

    def test_project_create_list_rename_and_ownership(self):
        r = self.bot.post("/api/v1/telegram/bot/projects/", {"telegram_id": 1001, "name": "Oshxona"}, format="json", **BOT)
        self.assertEqual(r.status_code, 201)
        pid = r.data["id"]
        self.assertEqual([p["name"] for p in self.get("/api/v1/telegram/bot/projects/").data], ["Oshxona"])
        r = self.bot.patch(f"/api/v1/telegram/bot/projects/{pid}/", {"telegram_id": 1001, "name": "Kitchen"}, format="json", **BOT)
        self.assertEqual(r.data["name"], "Kitchen")
        foreign = Project.objects.create(owner=self.other, name="Secret")
        r = self.bot.patch(f"/api/v1/telegram/bot/projects/{foreign.id}/", {"telegram_id": 1001, "name": "Hacked"}, format="json", **BOT)
        self.assertEqual(r.status_code, 404)
        foreign.refresh_from_db()
        self.assertEqual(foreign.name, "Secret")
        self.assertNotIn("Secret", [p["name"] for p in self.get("/api/v1/telegram/bot/projects/").data])

    def test_calculate_returns_engine_result_and_rejects_bad_input(self):
        r = self.bot.post("/api/v1/telegram/bot/calculate/", {"telegram_id": 1001, **CAB}, format="json", **BOT)
        self.assertEqual(r.status_code, 200)
        self.assertGreater(r.data["summary"]["total_area_m2"], 0)
        self.assertTrue(r.data["requires_professional_review"])
        bad = self.bot.post("/api/v1/telegram/bot/calculate/", {"telegram_id": 1001, **{**CAB, "width": 0}}, format="json", **BOT)
        self.assertEqual(bad.status_code, 400)

    def test_cutting_list_is_created_optimized_and_exported(self):
        r = self.bot.post("/api/v1/telegram/bot/cutting-lists/", {"telegram_id": 1001, "name": "Shkaf", **CAB}, format="json", **BOT)
        self.assertEqual(r.status_code, 201)
        self.assertGreater(r.data["parts_count"], 0)
        self.assertGreaterEqual(r.data["sheet_count"], 1)
        cid = r.data["id"]
        pdf = self.get(f"/api/v1/telegram/bot/cutting-lists/{cid}/export/pdf/")
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        xlsx = self.get(f"/api/v1/telegram/bot/cutting-lists/{cid}/export/xlsx/")
        self.assertEqual(xlsx.status_code, 200)
        self.assertEqual(self.get(f"/api/v1/telegram/bot/cutting-lists/{cid}/export/exe/").status_code, 404)

    def test_user_cannot_export_another_users_cutting_list(self):
        foreign = CuttingList.objects.create(owner=self.other, name="Other")
        self.assertEqual(self.get(f"/api/v1/telegram/bot/cutting-lists/{foreign.id}/export/pdf/").status_code, 404)

    def test_file_upload_validates_content(self):
        good = SimpleUploadedFile("drawing.pdf", b"%PDF-1.4\n%test", content_type="application/pdf")
        r = self.bot.post("/api/v1/telegram/bot/files/", {"telegram_id": 1001, "file": good}, format="multipart", **BOT)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["kind"], "pdf")
        fake_pdf = SimpleUploadedFile("evil.pdf", b"MZ\x90\x00 not a pdf", content_type="application/pdf")
        self.assertEqual(self.bot.post("/api/v1/telegram/bot/files/", {"telegram_id": 1001, "file": fake_pdf},
                                       format="multipart", **BOT).status_code, 400)
        exe = SimpleUploadedFile("run.exe", b"MZ", content_type="application/octet-stream")
        self.assertEqual(self.bot.post("/api/v1/telegram/bot/files/", {"telegram_id": 1001, "file": exe},
                                       format="multipart", **BOT).status_code, 400)

    def test_notifications_list_is_limited_to_unread(self):
        for i in range(7):
            Notification.objects.create(user=self.user, title=f"n{i}")
        self.assertEqual(len(self.get("/api/v1/telegram/bot/notifications/").data), 5)

    def test_unlink_via_bot(self):
        self.bot.post("/api/v1/telegram/bot/unlink/", {"telegram_id": 1001}, format="json", **BOT)
        self.assertFalse(TelegramLink.objects.filter(user=self.user).exists())
        self.assertEqual(self.get("/api/v1/telegram/bot/me/").status_code, 404)


@override_settings(TELEGRAM_BOT_API_SECRET=SECRET)
class BotAdminTests(TestCase):
    def setUp(self):
        self.user = make_user("u@x.com")
        self.admin = make_user("admin@x.com", is_staff=True, is_superuser=True)
        TelegramLink.objects.create(user=self.user, telegram_id=2001)
        TelegramLink.objects.create(user=self.admin, telegram_id=2002)
        self.bot = bot_client()

    def test_non_staff_cannot_use_admin_commands(self):
        r = self.bot.get("/api/v1/telegram/bot/admin/stats/?telegram_id=2001", **BOT)
        self.assertEqual(r.status_code, 403)
        r = self.bot.post("/api/v1/telegram/bot/admin/broadcast/", {"telegram_id": 2001, "text": "hi"}, format="json", **BOT)
        self.assertEqual(r.status_code, 403)

    def test_staff_stats_and_system_status(self):
        r = self.bot.get("/api/v1/telegram/bot/admin/stats/?telegram_id=2002", **BOT)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["telegram_linked"], 2)
        s = self.bot.get("/api/v1/telegram/bot/admin/system/?telegram_id=2002", **BOT)
        self.assertEqual(s.status_code, 200)
        self.assertIn("database", s.data)
        self.assertNotIn("password", str(s.data).lower())

    @mock.patch("apps.integrations.services.httpx.post")
    @override_settings(TELEGRAM_BOT_TOKEN="123:fake")
    def test_staff_broadcast_reaches_linked_chats(self, post):
        post.return_value = mock.Mock(status_code=200)
        r = self.bot.post("/api/v1/telegram/bot/admin/broadcast/", {"telegram_id": 2002, "text": "Yangilanish"}, format="json", **BOT)
        self.assertEqual(r.status_code, 202)
        chat_ids = sorted(c.kwargs["json"]["chat_id"] for c in post.call_args_list)
        self.assertEqual(chat_ids, [2001, 2002])


@override_settings(TELEGRAM_BOT_TOKEN="123:fake")
class TelegramPushTests(TestCase):
    def setUp(self):
        self.user = make_user("u@x.com")
        TelegramLink.objects.create(user=self.user, telegram_id=3001)

    @mock.patch("apps.integrations.services.httpx.post")
    def test_notification_is_mirrored_to_linked_chat(self, post):
        post.return_value = mock.Mock(status_code=200)
        notify_user_on_telegram.apply(args=(self.user.id, "Hisoblash tayyor", "Shkaf: 3 ta plita"))
        post.assert_called_once()
        self.assertIn("/bot123:fake/sendMessage", post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs["json"]["chat_id"], 3001)

    @mock.patch("apps.integrations.services.httpx.post")
    def test_user_without_link_gets_no_telegram_message(self, post):
        stranger = make_user("s@x.com")
        self.assertFalse(notify_user_on_telegram.apply(args=(stranger.id, "x")).get())
        post.assert_not_called()

    @mock.patch("apps.integrations.services.httpx.post")
    def test_telegram_failure_never_breaks_the_action(self, post):
        post.side_effect = httpx.ConnectError("down")
        self.assertFalse(services.telegram_api_send(3001, "x"))

    @mock.patch("apps.integrations.services.httpx.post")
    def test_web_notification_triggers_telegram_after_commit(self, post):
        post.return_value = mock.Mock(status_code=200)
        from apps.notifications.services import notify
        with self.captureOnCommitCallbacks(execute=True):
            notify(self.user, "Yangi xabar", "Matn")
        post.assert_called_once()
        self.assertEqual(post.call_args.kwargs["json"]["chat_id"], 3001)
