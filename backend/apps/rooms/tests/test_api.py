import shutil
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from apps.core.tests.helpers import client_for, make_user
from apps.designs.models import Design
from apps.galleries.models import GalleryImage
from apps.rooms.models import RoomFlow
from apps.rooms.services import MAX_ACTIVE_FLOWS

URL = "/api/v1/rooms/"
SIZE = {"width": 4000, "length": 3000, "height": 2700}
DOOR = {"type": "door", "wall": "north", "offset": 1000, "width": 900, "height": 2100, "sill": 0}
WINDOW = {"type": "window", "wall": "east", "offset": 800, "width": 1200, "height": 1200, "sill": 900}
TMP = tempfile.mkdtemp()


def png():
    b = BytesIO(); Image.new("RGB", (20, 10), "red").save(b, "PNG")
    return SimpleUploadedFile("room.png", b.getvalue(), content_type="image/png")


class RoomApiBase(TestCase):
    def setUp(self):
        self.a, self.b = make_user("a@x.com", "homeowner"), make_user("b@x.com", "homeowner")
        self.ca, self.cb = client_for(self.a), client_for(self.b)

    def start(self, c=None):
        r = (c or self.ca).post(URL)
        self.assertEqual(r.status_code, 201, r.data)
        return r.data["id"]

    def answer(self, rid, step, value, c=None, expect=200):
        r = (c or self.ca).post(f"{URL}{rid}/answer/", {"step": step, "value": value}, format="json")
        self.assertEqual(r.status_code, expect, r.data)
        return r.data

    def to_furnish(self, furniture=("bedside",), c=None, openings=True):
        rid = self.start(c)
        self.answer(rid, "goal", "bedroom", c)
        self.answer(rid, "photo", {"skip": True}, c)
        self.answer(rid, "elements", {"doors": 1 if openings else 0, "windows": 1 if openings else 0, "furniture": list(furniture)}, c)
        self.answer(rid, "size", SIZE, c)
        if openings:
            self.answer(rid, "openings", [DOOR, WINDOW], c)
        data = self.answer(rid, "style", "modern", c)
        return rid, data


class ConversationTests(RoomApiBase):
    def test_a_new_flow_starts_at_the_goal_question(self):
        r = self.ca.post(URL)
        self.assertEqual((r.status_code, r.data["status"], r.data["step"], r.data["design"], r.data["room"]), (201, "active", "goal", None, None))
        q = r.data["question"]
        self.assertEqual((q["kind"], q["index"], q["total"]), ("choice", 1, 7))
        self.assertEqual({o["id"] for o in q["options"]}, {"kitchen", "bedroom", "living", "wardrobe", "office", "other"})

    def test_the_full_journey_builds_a_saved_interior_design(self):
        rid, data = self.to_furnish()
        self.assertEqual((data["step"], data["question"]["kind"]), ("furnish", "furnish"))
        d = Design.objects.get(pk=data["design"])
        self.assertEqual((d.owner, d.kind, d.config["schema"], d.config["style"], d.config["goal"]), (self.a, "interior", "room.v1", "modern", "bedroom"))
        self.assertEqual([i["template"] for i in d.config["items"]], ["bedside"])
        self.assertEqual(d.config["colors"]["wall"], "#cbd5e1")
        self.assertEqual(data["room"]["config"]["room"], SIZE)
        done = self.ca.post(f"{URL}{rid}/finish/")
        self.assertEqual((done.status_code, done.data["status"], done.data["step"]), (200, "completed", "done"))

    def test_openings_are_skipped_when_there_are_none(self):
        rid, data = self.to_furnish(openings=False)
        self.assertEqual(data["step"], "furnish")
        self.assertEqual(data["room"]["config"]["openings"], [])

    def test_answering_the_wrong_step_is_a_conflict_that_names_the_expected_step(self):
        rid = self.start()
        r = self.ca.post(f"{URL}{rid}/answer/", {"step": "size", "value": SIZE}, format="json")
        self.assertEqual((r.status_code, r.data["error"]["expected_step"]), (409, "goal"))
        self.assertEqual(RoomFlow.objects.get(pk=rid).step, "goal")

    def test_bad_values_are_400_with_field_messages_and_change_nothing(self):
        rid = self.start()
        r = self.answer(rid, "goal", "spaceship", expect=400)
        self.assertIn("value", r["error"]["fields"])
        self.answer(rid, "goal", "kitchen"); self.answer(rid, "photo", {"skip": True})
        self.answer(rid, "elements", {"doors": 9, "windows": 0, "furniture": []}, expect=400)
        self.answer(rid, "elements", {"doors": 0, "windows": 0, "furniture": ["not-a-template"]}, expect=400)
        self.assertEqual(RoomFlow.objects.get(pk=rid).step, "elements")

    def test_impossible_room_sizes_and_openings_are_rejected(self):
        rid = self.start()
        self.answer(rid, "goal", "living"); self.answer(rid, "photo", {"skip": True}); self.answer(rid, "elements", {"doors": 1, "windows": 0, "furniture": []})
        self.answer(rid, "size", {"width": 100, "length": 3000, "height": 2700}, expect=400)
        self.answer(rid, "size", SIZE)
        self.answer(rid, "openings", [{**DOOR, "offset": 3900}], expect=400)             # runs off the wall
        self.answer(rid, "openings", [], expect=400)                                       # one door was promised

    def test_malformed_requests(self):
        rid = self.start()
        for body in ({}, {"step": "goal"}, {"value": "x"}, {"step": 5, "value": "x"}):
            self.assertEqual(self.ca.post(f"{URL}{rid}/answer/", body, format="json").status_code, 400, body)

    def test_back_keeps_the_answers_and_the_goal_has_no_earlier_step(self):
        rid, _ = self.to_furnish()
        r = self.ca.post(f"{URL}{rid}/back/")
        self.assertEqual((r.status_code, r.data["step"]), (200, "style"))
        self.assertIn("size", r.data["answers"])
        self.assertEqual(self.ca.post(f"{URL}{self.start()}/back/").status_code, 409)

    def test_answering_style_again_rebuilds_the_same_design_with_the_new_colours(self):
        rid, first = self.to_furnish()
        self.ca.post(f"{URL}{rid}/back/")
        again = self.answer(rid, "style", "luxury")
        self.assertEqual(again["design"], first["design"])
        self.assertEqual(Design.objects.count(), 1)
        self.assertEqual(Design.objects.get().config["colors"]["wall"], "#94a3b8")

    def test_a_finished_flow_is_frozen(self):
        rid, _ = self.to_furnish()
        self.ca.post(f"{URL}{rid}/finish/")
        self.assertEqual(self.ca.post(f"{URL}{rid}/back/").status_code, 409)
        self.assertEqual(self.ca.post(f"{URL}{rid}/items/", {"template": "bedside"}, format="json").status_code, 409)
        self.assertEqual(self.ca.post(f"{URL}{rid}/finish/").status_code, 409)

    def test_finish_needs_the_furnish_step(self):
        self.assertEqual(self.ca.post(f"{URL}{self.start()}/finish/").status_code, 409)

    def test_the_number_of_unfinished_designs_is_limited(self):
        for _ in range(MAX_ACTIVE_FLOWS):
            self.start()
        self.assertEqual(self.ca.post(URL).status_code, 409)
        self.assertEqual(client_for(self.b).post(URL).status_code, 201)

    def test_list_is_paginated_filterable_and_newest_first(self):
        first, second = self.start(), self.start()
        self.ca.post(f"{URL}{first}/answer/", {"step": "goal", "value": "office"}, format="json")
        r = self.ca.get(URL)
        self.assertEqual([x["id"] for x in r.data["results"]], [first, second])         # ordered by last activity: answering touched `first`
        self.assertEqual(r.data["results"][0]["goal"], "office")
        self.assertEqual(self.ca.get(URL, {"status": "completed"}).data["count"], 0)

    def test_delete_removes_the_flow_but_keeps_the_saved_design(self):
        rid, data = self.to_furnish()
        self.assertEqual(self.ca.delete(f"{URL}{rid}/").status_code, 204)
        self.assertEqual(RoomFlow.objects.count(), 0)
        self.assertTrue(Design.objects.filter(pk=data["design"]).exists())


@override_settings(MEDIA_ROOT=TMP)
class PhotoTests(RoomApiBase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def test_my_photo_is_kept_as_a_reference_and_linked_to_the_design(self):
        gid = self.ca.post("/api/v1/gallery/", {"image": png(), "source": "room"}, format="multipart").data["id"]
        rid = self.start()
        self.answer(rid, "goal", "bedroom")
        self.answer(rid, "photo", {"image_id": gid})
        self.answer(rid, "elements", {"doors": 0, "windows": 0, "furniture": []}); self.answer(rid, "size", SIZE)
        data = self.answer(rid, "style", "minimal")
        self.assertEqual(Design.objects.get(pk=data["design"]).room_image_id, gid)
        self.assertEqual(RoomFlow.objects.get(pk=rid).photo_id, gid)

    def test_someone_elses_photo_is_refused(self):
        gid = self.cb.post("/api/v1/gallery/", {"image": png()}, format="multipart").data["id"]
        rid = self.start()
        self.answer(rid, "goal", "bedroom")
        r = self.answer(rid, "photo", {"image_id": gid}, expect=400)
        self.assertIn("image_id", r["error"]["fields"])
        self.assertEqual(RoomFlow.objects.get(pk=rid).step, "photo")
        self.answer(rid, "photo", {"image_id": 999999}, expect=400)


class IsolationTests(RoomApiBase):
    def test_anonymous_users_are_refused(self):
        rid, _ = self.to_furnish()
        anon = APIClient()
        for call in (anon.get(URL), anon.post(URL), anon.get(f"{URL}{rid}/"), anon.get(f"{URL}{rid}/model/"), anon.delete(f"{URL}{rid}/")):
            self.assertEqual(call.status_code, 401)

    def test_another_user_gets_404_on_every_route_and_changes_nothing(self):
        rid, data = self.to_furnish()
        item = data["room"]["config"]["items"][0]["id"]
        before = Design.objects.get().config
        calls = [self.cb.get(f"{URL}{rid}/"), self.cb.delete(f"{URL}{rid}/"), self.cb.post(f"{URL}{rid}/back/"), self.cb.post(f"{URL}{rid}/finish/"),
                 self.cb.get(f"{URL}{rid}/model/"), self.cb.post(f"{URL}{rid}/reset-layout/"),
                 self.cb.post(f"{URL}{rid}/answer/", {"step": "furnish", "value": {"done": True}}, format="json"),
                 self.cb.post(f"{URL}{rid}/items/", {"template": "bedside"}, format="json"),
                 self.cb.patch(f"{URL}{rid}/items/{item}/", {"x": 0}, format="json"), self.cb.delete(f"{URL}{rid}/items/{item}/")]
        self.assertEqual([c.status_code for c in calls], [404] * len(calls))
        self.assertEqual(self.cb.get(URL).data["count"], 0)
        self.assertEqual(Design.objects.get().config, before)
        self.assertEqual(RoomFlow.objects.get().status, "active")


class FurnishTests(RoomApiBase):
    def setUp(self):
        super().setUp()
        self.rid, data = self.to_furnish(furniture=("bedside",))
        self.item = data["room"]["config"]["items"][0]

    def items(self):
        return Design.objects.get().config["items"]

    def test_the_layout_made_from_the_chosen_furniture_is_valid(self):
        self.assertEqual((self.item["template"], self.item["width"], self.item["depth"]), ("bedside", 450, 400))
        self.assertEqual(self.item["color"], "#e5e7eb")

    def test_adding_without_a_position_places_the_item_automatically_and_keeps_it_clear_of_others(self):
        r = self.ca.post(f"{URL}{self.rid}/items/", {"template": "dresser"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(len(self.items()), 2)
        a, b = self.items()
        self.assertEqual(r.data["item"]["id"], b["id"])
        fa, fb = (a["x"], a["z"], a["x"] + a["width"], a["z"] + a["depth"]), (b["x"], b["z"], b["x"] + b["width"], b["z"] + b["depth"])
        self.assertTrue(fa[2] <= fb[0] or fb[2] <= fa[0] or fa[3] <= fb[1] or fb[3] <= fa[1], (fa, fb))     # footprints do not overlap
        self.assertTrue(0 <= fb[0] and 0 <= fb[1] and fb[2] <= 4000 and fb[3] <= 3000)                     # and the new one is inside the room

    def test_adding_at_a_position_overrides_size_and_colour(self):
        r = self.ca.post(f"{URL}{self.rid}/items/", {"template": "bookcase", "x": 2500, "z": 1500, "rot": 90, "width": 900, "color": "#112233"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        it = r.data["item"]
        self.assertEqual((it["x"], it["z"], it["rot"], it["width"], it["color"], it["height"]), (2500, 1500, 90, 900, "#112233", 1800))

    def test_invalid_items_are_400_and_leave_the_room_unchanged(self):
        n = len(self.items())
        bad = [{"template": "nope"}, {}, {"template": "bedside", "x": -50, "z": 0}, {"template": "bedside", "x": 3900, "z": 0},
               {"template": "bedside", "x": 0, "z": 0, "rot": 45}, {"template": "bedside", "x": 0, "z": 0, "color": "red"}, {"template": "bedside", "x": 0, "z": 0, "height": 99999},
               {"template": "bedside", "hack": 1}, {"template": "bedside", "x": self.item["x"], "z": self.item["z"]}]    # last one overlaps the existing item
        for body in bad:
            self.assertEqual(self.ca.post(f"{URL}{self.rid}/items/", body, format="json").status_code, 400, body)
        self.assertEqual(self.ca.post(f"{URL}{self.rid}/items/", [1], format="json").status_code, 400)
        self.assertEqual(len(self.items()), n)

    def test_an_item_that_fits_nowhere_is_refused(self):
        r = self.ca.post(f"{URL}{self.rid}/items/", {"template": "wardrobe-3door", "width": 3900, "depth": 2900}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("position", r.data["error"]["fields"])

    def test_move_rotate_resize(self):
        r = self.ca.patch(f"{URL}{self.rid}/items/{self.item['id']}/", {"x": 2000, "z": 1200, "rot": 180, "width": 500}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        it = self.items()[0]
        self.assertEqual((it["x"], it["z"], it["rot"], it["width"], it["id"], it["template"]), (2000, 1200, 180, 500, self.item["id"], "bedside"))

    def test_the_id_and_template_of_an_item_cannot_be_changed(self):
        for body in ({"id": "x"}, {"template": "dresser"}, {"owner": 1}, {}):
            self.assertEqual(self.ca.patch(f"{URL}{self.rid}/items/{self.item['id']}/", body, format="json").status_code, 400, body)
        self.assertEqual(self.items()[0], self.item)

    def test_moving_an_item_out_of_the_room_or_onto_another_is_refused(self):
        self.ca.post(f"{URL}{self.rid}/items/", {"template": "dresser", "x": 2500, "z": 2000}, format="json")
        other = self.items()[1]
        self.assertEqual(self.ca.patch(f"{URL}{self.rid}/items/{self.item['id']}/", {"x": 3990}, format="json").status_code, 400)
        self.assertEqual(self.ca.patch(f"{URL}{self.rid}/items/{self.item['id']}/", {"x": other["x"], "z": other["z"]}, format="json").status_code, 400)
        self.assertEqual(self.items()[0], self.item)

    def test_blocking_a_door_is_a_warning_not_an_error(self):
        r = self.ca.patch(f"{URL}{self.rid}/items/{self.item['id']}/", {"x": 1100, "z": 0, "rot": 0}, format="json")      # in front of the north door
        self.assertEqual(r.status_code, 200)
        self.assertEqual([w["code"] for w in r.data["item_warnings"]], ["door_zone"])
        self.assertIn("door_zone", [w["code"] for w in r.data["room"]["warnings"]])

    def test_unknown_items_are_404(self):
        self.assertEqual(self.ca.patch(f"{URL}{self.rid}/items/ffffffffffff/", {"x": 1}, format="json").status_code, 404)
        self.assertEqual(self.ca.delete(f"{URL}{self.rid}/items/ffffffffffff/").status_code, 404)

    def test_remove_item_and_reset_layout(self):
        self.assertEqual(self.ca.delete(f"{URL}{self.rid}/items/{self.item['id']}/").status_code, 200)
        self.assertEqual(self.items(), [])
        self.ca.post(f"{URL}{self.rid}/items/", {"template": "dresser"}, format="json")
        r = self.ca.post(f"{URL}{self.rid}/reset-layout/")
        self.assertEqual([i["template"] for i in r.data["room"]["config"]["items"]], ["bedside"])

    def test_the_item_limit_is_enforced(self):
        from apps.geometry import room as geo
        d = Design.objects.get(); d.config["items"] = [{**self.item, "id": f"i{n}"} for n in range(geo.MAX_ITEMS)]; d.save()
        r = self.ca.post(f"{URL}{self.rid}/items/", {"template": "bedside"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("items", r.data["error"]["fields"])

    def test_furniture_cannot_be_changed_before_the_furnish_step(self):
        rid = self.start()
        self.assertEqual(self.ca.post(f"{URL}{rid}/items/", {"template": "bedside"}, format="json").status_code, 409)
        self.assertEqual(self.ca.get(f"{URL}{rid}/model/").status_code, 409)

    def test_the_3d_model_is_rebuilt_from_the_saved_config(self):
        r = self.ca.get(f"{URL}{self.rid}/model/")
        self.assertEqual(r.status_code, 200)
        kinds = {b["kind"] for b in r.data["boxes"]}
        self.assertTrue({"floor", "ceiling"} <= kinds)
        self.assertTrue(any(b.get("item") == self.item["id"] for b in r.data["boxes"]))
        self.assertEqual(r.data["dimensions"]["width"], 4000)
        self.ca.delete(f"{URL}{self.rid}/items/{self.item['id']}/")
        after = self.ca.get(f"{URL}{self.rid}/model/").data
        self.assertFalse(any(b.get("item") == self.item["id"] for b in after["boxes"]))

    def test_the_saved_design_is_the_same_document_the_api_shows(self):
        self.ca.post(f"{URL}{self.rid}/items/", {"template": "dresser"}, format="json")
        r = self.ca.get(f"{URL}{self.rid}/")
        self.assertEqual(r.data["room"]["config"], Design.objects.get().config)
        self.assertEqual(self.ca.get(f"/api/v1/designs/{r.data['design']}/").data["config"]["schema"], "room.v1")


class DesignLinkTests(RoomApiBase):
    def test_a_design_built_by_a_flow_points_back_to_it_and_others_do_not(self):
        rid, data = self.to_furnish()
        plain = Design.objects.create(owner=self.a, name="Plain", config={})
        r = self.ca.get("/api/v1/designs/")
        by_id = {d["id"]: d["room_flow"] for d in r.data["results"]}
        self.assertEqual(by_id, {data["design"]: rid, plain.pk: None})
        self.assertEqual(self.ca.get(f"/api/v1/designs/{data['design']}/").data["room_flow"], rid)
        self.assertEqual(self.ca.patch(f"/api/v1/designs/{data['design']}/", {"room_flow": 999}, format="json").data["room_flow"], rid)   # read-only

    def test_listing_designs_does_not_cost_a_query_per_design(self):
        for _ in range(3):
            self.to_furnish()
        with self.assertNumQueries(2):
            self.ca.get("/api/v1/designs/")
        for _ in range(3):
            self.to_furnish()
        with self.assertNumQueries(2):
            self.ca.get("/api/v1/designs/")
