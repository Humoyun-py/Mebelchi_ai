from django.test import SimpleTestCase, TestCase

from apps.conversations import assistant
from apps.core.tests.helpers import client_for, make_user


class AssistantTests(SimpleTestCase):
    def test_parse(self):
        p = assistant.parse("Cabinet 800x2000x400 with 3 shelves and 2 doors, 16 mm board")
        self.assertEqual((p["width"], p["height"], p["depth"], p["shelves"], p["doors"], p["thickness"]), (800, 2000, 400, 3, 2, 16))
        p = assistant.parse("width 900 height 720 depth 560 2 drawers")
        self.assertEqual((p["width"], p["depth"], p["drawers"]), (900, 560, 2))
        self.assertEqual(assistant.parse("800 × 2000 × 400 mm")["height"], 2000)

    def test_calculation_reply(self):
        text, meta = assistant.respond("cabinet 800x2000x400 with 3 shelves and 2 doors")
        self.assertEqual(meta["intent"], "calculation")
        self.assertIn("| Side panel |", text)
        self.assertIn("professional review", text)

    def test_cutting_includes_optimization(self):
        _, meta = assistant.respond("cutting list for wardrobe 1000x2200x580 4 shelves 2 doors")
        self.assertIn("optimization", meta)

    def test_honest_about_limits(self):
        text, meta = assistant.respond("design me a luxury kitchen in the style of Zaha Hadid")
        self.assertEqual(meta["intent"], "unsupported")
        self.assertIn("rule-based", text)
        text, meta = assistant.respond("cabinet 800x2000", [{"type": "image", "id": 1, "name": "sketch.png"}])
        self.assertEqual(meta["intent"], "need_input")
        self.assertIn("not implemented", text)

    def test_invalid_dimensions_explained(self):
        text, meta = assistant.respond("cabinet 50x2000x400")
        self.assertEqual(meta["intent"], "invalid_input")
        self.assertIn("width", text)

    def test_help(self):
        self.assertEqual(assistant.respond("help")[1]["intent"], "help")


class ChatApiTests(TestCase):
    def setUp(self):
        self.a, self.b = make_user("a@x.com"), make_user("b@x.com")
        self.ca, self.cb = client_for(self.a), client_for(self.b)

    def test_flow(self):
        cid = self.ca.post("/api/v1/conversations/", {}, format="json").data["id"]
        r = self.ca.post(f"/api/v1/conversations/{cid}/messages/", {"content": "cabinet 800x2000x400 with 2 shelves"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        user_msg, bot = r.data
        self.assertEqual((user_msg["role"], bot["role"]), ("user", "assistant"))
        self.assertTrue(self.ca.get(f"/api/v1/conversations/{cid}/").data["title"].startswith("cabinet"))
        fb = self.ca.post(f"/api/v1/messages/{bot['id']}/feedback/", {"feedback": "like"}, format="json")
        self.assertEqual(fb.data["feedback"], "like")
        self.assertEqual(self.ca.post(f"/api/v1/messages/{bot['id']}/feedback/", {"feedback": "bogus"}, format="json").status_code, 400)
        edited = self.ca.patch(f"/api/v1/messages/{user_msg['id']}/", {"content": "cabinet 600x720x560 with 1 doors"}, format="json")
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(len(self.ca.get(f"/api/v1/conversations/{cid}/messages/").data), 2)
        regen = self.ca.post(f"/api/v1/messages/{edited.data[1]['id']}/regenerate/")
        self.assertEqual(regen.status_code, 201)
        self.assertEqual(self.ca.post(f"/api/v1/messages/{edited.data[0]['id']}/regenerate/").status_code, 400)
        self.assertIn("MEBELCHI AI", self.ca.get(f"/api/v1/conversations/{cid}/export/").content.decode())
        self.assertEqual(self.ca.delete(f"/api/v1/messages/{regen.data['id']}/").status_code, 204)

    def test_isolation_and_attachment_ownership(self):
        cid = self.ca.post("/api/v1/conversations/", {}, format="json").data["id"]
        self.ca.post(f"/api/v1/conversations/{cid}/messages/", {"content": "help"}, format="json")
        mid = self.ca.get(f"/api/v1/conversations/{cid}/messages/").data[0]["id"]
        self.assertEqual(self.cb.get(f"/api/v1/conversations/{cid}/messages/").status_code, 404)
        self.assertEqual(self.cb.post(f"/api/v1/conversations/{cid}/messages/", {"content": "hi"}, format="json").status_code, 404)
        self.assertEqual(self.cb.patch(f"/api/v1/messages/{mid}/", {"content": "x"}, format="json").status_code, 404)
        self.assertEqual(self.cb.delete(f"/api/v1/messages/{mid}/").status_code, 404)
        self.assertEqual(self.ca.post(f"/api/v1/conversations/{cid}/messages/", {"content": "hi", "attachments": [{"type": "image", "id": 999}]}, format="json").status_code, 400)
        self.assertEqual(self.ca.post(f"/api/v1/conversations/{cid}/messages/", {"content": ""}, format="json").status_code, 400)
