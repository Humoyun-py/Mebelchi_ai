import shutil
import tempfile

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.core.tests.helpers import make_user
from apps.designs.models import Design
from apps.galleries.models import GalleryImage
from apps.integrations.models import TelegramLink
from apps.rooms.models import RoomFlow

from .helpers import DOOR, ELEMENTS, SIZE, WINDOW, err_code, png

SECRET = "test-bot-secret-value"
BOT = {"HTTP_X_BOT_SECRET": SECRET}
BASE = "/api/v1/telegram/bot/room-flows/"
TMP_MEDIA = tempfile.mkdtemp(prefix="rooms-bot-media-")


def tearDownModule():
    shutil.rmtree(TMP_MEDIA, ignore_errors=True)


@override_settings(TELEGRAM_BOT_API_SECRET=SECRET, MEDIA_ROOT=TMP_MEDIA)
class BotRoomFlowTests(TestCase):
    TG_A, TG_B = 1001, 2002

    def setUp(self):
        cache.clear()
        self.a, self.b = make_user("a@example.com"), make_user("b@example.com", role="maker")
        TelegramLink.objects.create(user=self.a, telegram_id=self.TG_A, username="a")
        TelegramLink.objects.create(user=self.b, telegram_id=self.TG_B, username="b")
        self.bot = APIClient()

    # -- helpers ------------------------------------------------------------------------------------------------
    def post(self, path, body=None, tg=None, expect=200, **kw):
        r = self.bot.post(BASE + path, {"telegram_id": tg or self.TG_A, **(body or {})}, format="json", **BOT, **kw)
        self.assertEqual(r.status_code, expect, r.data)
        return r

    def get(self, path, tg=None, expect=200, extra=""):
        r = self.bot.get(f"{BASE}{path}?telegram_id={tg or self.TG_A}{extra}", **BOT)
        self.assertEqual(r.status_code, expect, r.data)
        return r

    def start(self, tg=None, **body):
        return self.post("", body, tg, expect=201).data["id"]

    def answer(self, fid, step, value, tg=None, expect=200):
        return self.post(f"{fid}/answer/", {"step": step, "value": value}, tg, expect)

    def to_furnish(self, tg=None):
        fid = self.start(tg)
        for step, value in (("goal", "bedroom"), ("photo", {"skip": True}), ("elements", ELEMENTS), ("size", SIZE), ("openings", [DOOR, WINDOW])):
            self.answer(fid, step, value, tg)
        return fid, self.answer(fid, "style", "modern", tg).data

    # -- authentication ---------------------------------------------------------------------------------------
    def test_secret_is_required_on_every_endpoint(self):
        fid = self.start()
        calls = [("post", BASE, {"telegram_id": self.TG_A}), ("get", f"{BASE}{fid}/?telegram_id={self.TG_A}", None),
                 ("post", f"{BASE}{fid}/answer/", {"telegram_id": self.TG_A, "step": "goal", "value": "kitchen"}),
                 ("post", f"{BASE}{fid}/back/", {"telegram_id": self.TG_A}), ("post", f"{BASE}{fid}/abandon/", {"telegram_id": self.TG_A}),
                 ("get", f"{BASE}{fid}/model/?telegram_id={self.TG_A}", None), ("post", f"{BASE}{fid}/items/", {"telegram_id": self.TG_A, "rev": 1}),
                 ("patch", f"{BASE}{fid}/items/{'0' * 12}/", {"telegram_id": self.TG_A, "rev": 1}), ("delete", f"{BASE}{fid}/items/{'0' * 12}/?telegram_id={self.TG_A}&rev=1", None),
                 ("post", f"{BASE}{fid}/photo/", {"telegram_id": self.TG_A})]
        for method, url, body in calls:
            for headers in ({}, {"HTTP_X_BOT_SECRET": "wrong"}):
                r = getattr(self.bot, method)(url, body, format="json", **headers) if body is not None else getattr(self.bot, method)(url, **headers)
                self.assertEqual(r.status_code, 403, (method, url, headers))

    @override_settings(TELEGRAM_BOT_API_SECRET="")
    def test_empty_secret_disables_the_endpoints(self):
        r = self.bot.post(BASE, {"telegram_id": self.TG_A}, format="json", **BOT)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.bot.post(BASE, {"telegram_id": self.TG_A}, format="json").status_code, 403)

    def test_a_user_session_cannot_call_bot_endpoints(self):
        web = APIClient()
        web.force_authenticate(self.a)
        self.assertEqual(web.post(BASE, {"telegram_id": self.TG_A}, format="json").status_code, 403)

    def test_unlinked_telegram_id_is_404(self):
        r = self.bot.post(BASE, {"telegram_id": 999}, format="json", **BOT)
        self.assertEqual((r.status_code, err_code(r)), (404, "not_linked"))
        fid = self.start()
        self.assertEqual(self.bot.get(f"{BASE}{fid}/?telegram_id=999", **BOT).status_code, 404)

    def test_telegram_id_is_mandatory_and_numeric(self):
        fid = self.start()
        self.assertEqual(self.bot.get(f"{BASE}{fid}/", **BOT).status_code, 400)
        self.assertEqual(self.bot.get(f"{BASE}{fid}/?telegram_id=abc", **BOT).status_code, 400)
        self.assertEqual(self.bot.post(BASE, {}, format="json", **BOT).status_code, 400)
        self.assertEqual(self.bot.patch(f"{BASE}{fid}/items/{'0' * 12}/", {"rev": 1}, format="json", **BOT).status_code, 400)

    # -- start, resume, restart ------------------------------------------------------------------------------
    def test_start_then_resume_returns_the_same_flow(self):
        first = self.post("", expect=201).data
        self.answer(first["id"], "goal", "office")
        again = self.post("", expect=200).data              # same account, a new request: the bot kept nothing
        self.assertEqual((again["id"], again["step"]), (first["id"], "photo"))
        self.assertEqual(again["answers"]["goal"], "office")
        self.assertEqual(RoomFlow.objects.filter(owner=self.a).count(), 1)

    def test_new_abandons_the_active_flow(self):
        old = self.start()
        fresh = self.post("", {"new": True}, expect=201).data
        self.assertNotEqual(old, fresh["id"])
        self.assertEqual(RoomFlow.objects.get(pk=old).status, "abandoned")
        self.assertEqual(self.post("", expect=200).data["id"], fresh["id"])

    def test_resume_ignores_completed_and_abandoned_flows(self):
        fid, _ = self.to_furnish()
        self.answer(fid, "furnish", {"done": True})
        self.assertNotEqual(self.post("", expect=201).data["id"], fid)

    def test_each_account_has_its_own_active_flow(self):
        a, b = self.start(), self.start(tg=self.TG_B)
        self.assertNotEqual(a, b)
        self.assertEqual(self.post("", tg=self.TG_B, expect=200).data["id"], b)

    # -- the journey ------------------------------------------------------------------------------------------
    def test_full_journey_through_the_bot_api(self):
        fid, data = self.to_furnish()
        self.assertEqual((data["step"], data["rev"], len(data["items"])), ("furnish", 1, 2))
        self.assertEqual(Design.objects.get(pk=data["design_id"]).owner, self.a)
        m = self.get(f"{fid}/model/").data
        self.assertEqual(m["dimensions"]["width"], 4000)
        self.assertTrue(m["requires_professional_review"])
        added = self.post(f"{fid}/items/", {"template": "bedside", "rev": 1}, expect=201).data
        self.assertEqual((added["rev"], len(added["items"])), (2, 3))
        item = added["item"]["id"]
        moved = self.bot.patch(f"{BASE}{fid}/items/{item}/", {"telegram_id": self.TG_A, "rot": 90, "rev": 2}, format="json", **BOT)
        self.assertEqual((moved.status_code, moved.data["item"]["rot"], moved.data["rev"]), (200, 90, 3))
        gone = self.bot.delete(f"{BASE}{fid}/items/{item}/?telegram_id={self.TG_A}&rev=3", **BOT)
        self.assertEqual((gone.status_code, len(gone.data["items"]), gone.data["rev"]), (200, 2, 4))
        done = self.answer(fid, "furnish", {"done": True}).data
        self.assertEqual((done["status"], done["step"]), ("completed", "done"))

    def test_state_is_recovered_after_the_bot_restarts(self):
        fid, _ = self.to_furnish()
        self.post(f"{fid}/items/", {"template": "bedside", "rev": 1}, expect=201)
        fresh_bot = APIClient()                                    # a restarted bot process holds nothing
        r = fresh_bot.post(BASE, {"telegram_id": self.TG_A}, format="json", **BOT)
        self.assertEqual((r.status_code, r.data["id"], r.data["step"], r.data["rev"], len(r.data["items"])), (200, fid, "furnish", 2, 3))

    def test_back_and_abandon(self):
        fid = self.start()
        self.answer(fid, "goal", "kitchen")
        self.assertEqual(self.post(f"{fid}/back/").data["step"], "goal")
        self.assertEqual(self.post(f"{fid}/abandon/").data["status"], "abandoned")
        self.post(f"{fid}/back/", expect=409)

    def test_validation_and_step_errors_use_the_standard_envelope(self):
        fid = self.start()
        r = self.answer(fid, "size", SIZE, expect=409)
        self.assertEqual((err_code(r), r.data["error"]["fields"]["expected"]), ("step_mismatch", "goal"))
        self.answer(fid, "goal", "nowhere", expect=400)
        self.assertEqual(self.get(f"{fid}/").data["step"], "goal")

    def test_rev_conflict_through_the_bot(self):
        fid, _ = self.to_furnish()
        self.post(f"{fid}/items/", {"template": "bedside", "rev": 1}, expect=201)
        r = self.post(f"{fid}/items/", {"template": "bedside", "rev": 1}, expect=409)
        self.assertEqual((err_code(r), r.data["error"]["fields"]["current_rev"]), ("rev_conflict", 2))

    # -- photo ------------------------------------------------------------------------------------------------
    def test_photo_upload_is_stored_in_the_gallery_and_answers_the_step(self):
        fid = self.start()
        self.answer(fid, "goal", "bedroom")
        r = self.bot.post(f"{BASE}{fid}/photo/", {"telegram_id": self.TG_A, "file": png()}, format="multipart", **BOT)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["step"], "elements")
        img = GalleryImage.objects.get(pk=r.data["photo_id"])
        self.assertEqual((img.owner, img.source, (img.width, img.height)), (self.a, "room", (40, 30)))

    def test_photo_at_the_wrong_step_is_409_and_stores_nothing(self):
        fid = self.start()
        r = self.bot.post(f"{BASE}{fid}/photo/", {"telegram_id": self.TG_A, "file": png()}, format="multipart", **BOT)
        self.assertEqual((r.status_code, err_code(r)), (409, "step_mismatch"))
        self.assertEqual(GalleryImage.objects.count(), 0)

    def test_a_file_that_is_not_an_image_is_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        fid = self.start()
        self.answer(fid, "goal", "bedroom")
        for f in (SimpleUploadedFile("evil.png", b"MZ not an image", content_type="image/png"), SimpleUploadedFile("note.txt", b"hello", content_type="text/plain")):
            r = self.bot.post(f"{BASE}{fid}/photo/", {"telegram_id": self.TG_A, "file": f}, format="multipart", **BOT)
            self.assertEqual(r.status_code, 400)
        self.assertEqual(GalleryImage.objects.count(), 0)
        self.assertEqual(RoomFlow.objects.get(pk=fid).step, "photo")

    # -- isolation --------------------------------------------------------------------------------------------
    def test_another_linked_account_gets_404_for_every_endpoint(self):
        fid, data = self.to_furnish()
        item = data["items"][0]["id"]
        B = self.TG_B
        for r in (self.bot.get(f"{BASE}{fid}/?telegram_id={B}", **BOT), self.bot.get(f"{BASE}{fid}/model/?telegram_id={B}", **BOT),
                  self.bot.post(f"{BASE}{fid}/answer/", {"telegram_id": B, "step": "furnish", "value": {"done": True}}, format="json", **BOT),
                  self.bot.post(f"{BASE}{fid}/back/", {"telegram_id": B}, format="json", **BOT), self.bot.post(f"{BASE}{fid}/abandon/", {"telegram_id": B}, format="json", **BOT),
                  self.bot.post(f"{BASE}{fid}/items/", {"telegram_id": B, "template": "bedside", "rev": 1}, format="json", **BOT),
                  self.bot.patch(f"{BASE}{fid}/items/{item}/", {"telegram_id": B, "x": 5, "rev": 1}, format="json", **BOT),
                  self.bot.delete(f"{BASE}{fid}/items/{item}/?telegram_id={B}&rev=1", **BOT),
                  self.bot.post(f"{BASE}{fid}/photo/", {"telegram_id": B, "file": png()}, format="multipart", **BOT)):
            self.assertEqual(r.status_code, 404, r.request["PATH_INFO"])
        self.assertEqual(RoomFlow.objects.get(pk=fid).status, "active")
        self.assertEqual(len(Design.objects.get(pk=data["design_id"]).config["items"]), 2)
        self.assertEqual(GalleryImage.objects.count(), 0)
