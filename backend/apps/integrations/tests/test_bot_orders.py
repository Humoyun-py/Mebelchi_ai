from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.core.tests.helpers import make_user
from apps.integrations import services as tg
from apps.integrations.models import TelegramLink
from apps.integrations.tasks import notify_user_on_telegram
from apps.workshops import services as ws_services
from apps.workshops.models import Order, Workshop

SECRET = "test-bot-secret-value"
BOT = {"HTTP_X_BOT_SECRET": SECRET}


def shop(email, tg_id):
    owner = make_user(email, role="workshop")
    ws = ws_services.create_workshop(owner, {"name": f"Shop {email}"})
    Workshop.objects.filter(pk=ws.pk).update(status="active")
    ws.refresh_from_db()
    TelegramLink.objects.create(user=owner, telegram_id=tg_id, username="x")
    return owner, ws


def order(owner, ws, status="pending", title="Kitchen"):
    o = ws_services.create_order(ws, owner, {"title": title, "customer_name": "Ali", "customer_phone": "+998901112233", "customer_address": "Tashkent", "total_price": 1500000})
    Order.objects.filter(pk=o.pk).update(status=status)
    return Order.objects.get(pk=o.pk)


@override_settings(TELEGRAM_BOT_API_SECRET=SECRET)
class BotOrderTests(TestCase):
    def setUp(self):
        cache.clear()
        self.bot = APIClient()
        self.owner, self.ws = shop("shop1@x.com", 1001)
        self.other, self.other_ws = shop("shop2@x.com", 1002)

    def get(self, path, tid, **q):
        return self.bot.get(f"/api/v1/telegram/bot/{path}", {"telegram_id": tid, **q}, **BOT)

    def post(self, path, body):
        return self.bot.post(f"/api/v1/telegram/bot/{path}", body, format="json", **BOT)

    def test_list_shows_only_my_orders_and_can_filter_by_status(self):
        mine = order(self.owner, self.ws)
        order(self.owner, self.ws, status="confirmed", title="Wardrobe")
        order(self.other, self.other_ws, title="Not mine")
        r = self.get("orders/", 1001)
        self.assertEqual(r.status_code, 200)
        self.assertEqual({o["title"] for o in r.data}, {"Kitchen", "Wardrobe"})
        r = self.get("orders/", 1001, status="pending")
        self.assertEqual([o["id"] for o in r.data], [mine.pk])
        self.assertIn("confirmed", r.data[0]["allowed_next_statuses"])
        self.assertEqual(r.data[0]["total_price"], "1500000.00")
        self.assertEqual(self.get("orders/", 1001, status="bogus").status_code, 400)

    def test_accept_moves_the_order_and_the_server_lists_the_next_steps(self):
        o = order(self.owner, self.ws)
        r = self.post(f"orders/{o.pk}/status/", {"telegram_id": 1001, "status": "confirmed"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "confirmed")
        self.assertIn("in_production", r.data["allowed_next_statuses"])
        o.refresh_from_db()
        self.assertEqual(o.status, "confirmed")

    def test_rejecting_needs_a_reason_and_keeps_it(self):
        o = order(self.owner, self.ws)
        r = self.post(f"orders/{o.pk}/status/", {"telegram_id": 1001, "status": "rejected"})
        self.assertEqual(r.status_code, 400)
        o.refresh_from_db()
        self.assertEqual(o.status, "pending")
        r = self.post(f"orders/{o.pk}/status/", {"telegram_id": 1001, "status": "rejected", "note": "Too far away"})
        self.assertEqual(r.status_code, 200)
        o.refresh_from_db()
        self.assertEqual((o.status, o.rejection_reason), ("rejected", "Too far away"))

    def test_an_illegal_jump_is_refused_and_changes_nothing(self):
        o = order(self.owner, self.ws)
        r = self.post(f"orders/{o.pk}/status/", {"telegram_id": 1001, "status": "delivered"})
        self.assertEqual(r.status_code, 400)
        o.refresh_from_db()
        self.assertEqual(o.status, "pending")
        self.assertEqual(self.post(f"orders/{o.pk}/status/", {"telegram_id": 1001, "status": "nonsense"}).status_code, 400)

    def test_another_workshop_cannot_see_or_change_my_order(self):
        o = order(self.owner, self.ws)
        self.assertEqual(self.get(f"orders/{o.pk}/", 1002).status_code, 404)
        self.assertEqual(self.post(f"orders/{o.pk}/status/", {"telegram_id": 1002, "status": "confirmed"}).status_code, 404)
        o.refresh_from_db()
        self.assertEqual(o.status, "pending")

    def test_unlinked_telegram_and_wrong_secret_are_refused(self):
        o = order(self.owner, self.ws)
        r = self.get(f"orders/{o.pk}/", 9999)
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.data["error"]["fields"]["code"], "not_linked")
        r = self.bot.get("/api/v1/telegram/bot/orders/", {"telegram_id": 1001}, HTTP_X_BOT_SECRET="wrong")
        self.assertIn(r.status_code, (401, 403))
        r = self.bot.get("/api/v1/telegram/bot/orders/", {"telegram_id": 1001})
        self.assertIn(r.status_code, (401, 403))

    def test_a_non_workshop_account_sees_no_orders(self):
        maker = make_user("m@x.com", role="maker")
        TelegramLink.objects.create(user=maker, telegram_id=2001, username="m")
        order(self.owner, self.ws)
        self.assertEqual(self.get("orders/", 2001).data, [])


@override_settings(TELEGRAM_BOT_API_SECRET=SECRET, TELEGRAM_BOT_TOKEN="123:abc")
class OrderPushTests(TestCase):
    def setUp(self):
        self.owner, self.ws = shop("shop3@x.com", 3001)

    def test_buttons_only_for_a_pending_order_of_the_owner(self):
        o = order(self.owner, self.ws)
        rows = tg.order_action_buttons(self.owner, o.pk)
        self.assertEqual([b["callback_data"] for b in rows[0]], [f"ord:acc:{o.pk}", f"ord:rej:{o.pk}"])
        self.assertEqual(rows[1][0]["callback_data"], f"ord:view:{o.pk}")
        stranger = make_user("s@x.com", role="maker")
        self.assertIsNone(tg.order_action_buttons(stranger, o.pk))
        Order.objects.filter(pk=o.pk).update(status="confirmed")
        self.assertIsNone(tg.order_action_buttons(self.owner, o.pk))
        self.assertIsNone(tg.order_action_buttons(self.owner, 99999))

    def test_button_labels_follow_the_user_language(self):
        self.owner.language = "ru"
        o = order(self.owner, self.ws)
        self.assertEqual(tg.order_action_buttons(self.owner, o.pk)[0][0]["text"], "Принять")

    @mock.patch("apps.integrations.services.httpx.post")
    def test_the_push_carries_inline_buttons_for_an_order_and_plain_text_otherwise(self, post):
        post.return_value = mock.Mock(status_code=200)
        o = order(self.owner, self.ws)
        notify_user_on_telegram(self.owner.pk, "New order", "Please answer", o.pk)
        sent = post.call_args.kwargs["json"]
        self.assertEqual(sent["chat_id"], 3001)
        self.assertEqual(sent["reply_markup"]["inline_keyboard"][0][0]["callback_data"], f"ord:acc:{o.pk}")
        notify_user_on_telegram(self.owner.pk, "Hello", "plain")
        self.assertNotIn("reply_markup", post.call_args.kwargs["json"])
