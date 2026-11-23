import shutil
import tempfile

from django.test import TestCase, override_settings

from apps.core.tests.helpers import client_for, make_user
from apps.designs.models import Design
from apps.galleries.models import GalleryImage
from apps.rooms.models import RoomFlow

from .helpers import DOOR, ELEMENTS, SIZE, WINDOW, err_code, png

API = "/api/v1/room-flows/"
TMP_MEDIA = tempfile.mkdtemp(prefix="rooms-test-media-")


def tearDownModule():
    shutil.rmtree(TMP_MEDIA, ignore_errors=True)


class Base(TestCase):
    def setUp(self):
        self.a, self.b = make_user("a@example.com"), make_user("b@example.com", role="maker")
        self.ca, self.cb = client_for(self.a), client_for(self.b)

    def start(self, client=None):
        r = (client or self.ca).post(API)
        self.assertEqual(r.status_code, 201, r.data)
        return r.data["id"]

    def answer(self, fid, step, value, client=None, expect=200):
        r = (client or self.ca).post(f"{API}{fid}/answer/", {"step": step, "value": value}, format="json")
        self.assertEqual(r.status_code, expect, r.data)
        return r

    def to_furnish(self, openings=(DOOR, WINDOW), elements=None, client=None):
        fid = self.start(client)
        self.answer(fid, "goal", "bedroom", client)
        self.answer(fid, "photo", {"skip": True}, client)
        self.answer(fid, "elements", elements or ELEMENTS, client)
        self.answer(fid, "size", SIZE, client)
        if openings:
            self.answer(fid, "openings", list(openings), client)
        r = self.answer(fid, "style", "modern", client)
        return fid, r.data

    def item_url(self, fid, item_id=""):
        return f"{API}{fid}/items/{item_id + '/' if item_id else ''}"


class JourneyTests(Base):
    def test_start_returns_the_first_question(self):
        r = self.ca.post(API)
        self.assertEqual(r.status_code, 201)
        self.assertEqual((r.data["status"], r.data["step"], r.data["descriptor"]["kind"]), ("active", "goal", "choice"))
        self.assertIsNone(r.data["design_id"])
        self.assertEqual(RoomFlow.objects.get(pk=r.data["id"]).owner, self.a)

    def test_full_journey_builds_a_room_and_a_design(self):
        fid, data = self.to_furnish()
        self.assertEqual((data["step"], data["descriptor"]["kind"]), ("furnish", "furnish"))
        self.assertEqual(data["rev"], 1)
        self.assertEqual(len(data["items"]), 2)
        self.assertEqual(data["warnings"], [])
        design = Design.objects.get(pk=data["design_id"])
        self.assertEqual((design.owner, design.kind), (self.a, "interior"))
        cfg = design.config
        self.assertEqual((cfg["schema"], cfg["goal"], cfg["style"], cfg["room"]), ("room.v1", "bedroom", "modern", SIZE))
        self.assertEqual(len(cfg["openings"]), 2)
        self.assertLess(len(str(cfg)), 200_000)
        m = self.ca.get(f"{API}{fid}/model/").data
        self.assertEqual(m["dimensions"]["width"], 4000)
        self.assertTrue(m["requires_professional_review"])
        self.assertEqual({b["kind"] for b in m["boxes"]} >= {"wall", "floor", "ceiling", "carcass"}, True)

    def test_journey_without_openings_skips_that_step(self):
        fid = self.start()
        self.answer(fid, "goal", "kitchen")
        self.answer(fid, "photo", {"skip": True})
        self.answer(fid, "elements", {"doors": 0, "windows": 0, "furniture": ["base-cabinet"]})
        r = self.answer(fid, "size", SIZE)
        self.assertEqual(r.data["step"], "style")
        self.assertEqual(self.answer(fid, "style", "minimal").data["step"], "furnish")

    def test_style_decides_the_wall_color_of_the_model(self):
        colors = {}
        for style in ("modern", "classic"):
            fid = self.start()
            for step, value in (("goal", "kitchen"), ("photo", {"skip": True}), ("elements", {}), ("size", SIZE), ("style", style)):
                self.answer(fid, step, value)
            walls = [b for b in self.ca.get(f"{API}{fid}/model/").data["boxes"] if b["kind"] == "wall"]
            colors[style] = {b["color"] for b in walls}
        self.assertEqual(colors, {"modern": {"#cbd5e1"}, "classic": {"#e7dcc8"}})

    def test_reentry_continues_where_the_user_stopped(self):
        fid = self.start()
        self.answer(fid, "goal", "office")
        self.answer(fid, "photo", {"skip": True})
        again = client_for(self.a)   # a new client: nothing is kept in memory, the state is in the database
        r = again.get(f"{API}{fid}/")
        self.assertEqual((r.data["step"], r.data["descriptor"]["step"]), ("elements", "elements"))
        self.assertEqual(r.data["answers"]["goal"], "office")
        listing = again.get(API + "?status=active").data
        self.assertEqual([f["id"] for f in listing["results"]], [fid])

    def test_back_keeps_answers(self):
        fid = self.start()
        self.answer(fid, "goal", "living")
        r = self.ca.post(f"{API}{fid}/back/")
        self.assertEqual(r.data["step"], "goal")
        self.assertEqual(r.data["answers"]["goal"], "living")
        self.assertEqual(r.data["descriptor"]["value"], "living")
        self.assertEqual(self.ca.post(f"{API}{fid}/back/").status_code, 409)

    def test_wrong_step_is_409_with_the_expected_step(self):
        fid = self.start()
        r = self.answer(fid, "size", SIZE, expect=409)
        self.assertEqual(err_code(r), "step_mismatch")
        self.assertEqual(r.data["error"]["fields"]["expected"], "goal")
        self.assertEqual(RoomFlow.objects.get(pk=fid).step, "goal")

    def test_invalid_value_is_400_and_leaves_the_state(self):
        fid = self.start()
        self.answer(fid, "goal", "kitchen")
        self.answer(fid, "photo", {"skip": True})
        self.answer(fid, "elements", {})
        for bad in ({**SIZE, "width": 999}, {**SIZE, "height": 5000}, {"width": 3000}):
            r = self.answer(fid, "size", bad, expect=400)
            self.assertTrue(r.data["error"]["fields"])
        self.assertEqual(RoomFlow.objects.get(pk=fid).step, "size")

    def test_impossible_openings_are_rejected(self):
        fid = self.start()
        self.answer(fid, "goal", "kitchen")
        self.answer(fid, "photo", {"skip": True})
        self.answer(fid, "elements", {"doors": 1, "windows": 1})
        self.answer(fid, "size", SIZE)
        for bad in ([{**DOOR, "offset": 3500}, WINDOW], [DOOR, {**WINDOW, "wall": "north", "offset": 1500}], [DOOR, {**WINDOW, "sill": 1500, "height": 1200}], [DOOR]):
            self.answer(fid, "openings", bad, expect=400)
        self.assertEqual(self.answer(fid, "openings", [DOOR, WINDOW]).data["step"], "style")

    def test_unknown_step_and_missing_value(self):
        fid = self.start()
        self.assertEqual(self.ca.post(f"{API}{fid}/answer/", {"step": "nope", "value": 1}, format="json").status_code, 400)
        self.assertEqual(self.ca.post(f"{API}{fid}/answer/", {"step": "goal"}, format="json").status_code, 400)

    def test_generate_and_done_are_not_answerable(self):
        fid = self.start()
        self.assertEqual(self.ca.post(f"{API}{fid}/answer/", {"step": "generate", "value": 1}, format="json").status_code, 400)

    def test_completing_locks_the_flow(self):
        fid, data = self.to_furnish()
        r = self.answer(fid, "furnish", {"done": True})
        self.assertEqual((r.data["status"], r.data["step"]), ("completed", "done"))
        self.assertEqual(self.ca.get(f"{API}{fid}/").status_code, 200)
        self.assertEqual(err_code(self.ca.post(f"{API}{fid}/back/")), "not_active")
        self.assertEqual(err_code(self.ca.post(self.item_url(fid), {"template": "bedside", "rev": r.data["rev"]}, format="json")), "not_active")
        self.assertEqual(self.ca.post(f"{API}{fid}/abandon/").status_code, 409)

    def test_abandon(self):
        fid = self.start()
        self.assertEqual(self.ca.post(f"{API}{fid}/abandon/").data["status"], "abandoned")
        self.assertEqual(self.ca.get(API + "?status=active").data["count"], 0)
        self.assertEqual(err_code(self.ca.post(f"{API}{fid}/answer/", {"step": "goal", "value": "kitchen"}, format="json")), "not_active")

    def test_model_before_generation_is_409(self):
        fid = self.start()
        self.assertEqual(err_code(self.ca.get(f"{API}{fid}/model/")), "not_generated")

    def test_changing_the_style_after_going_back_rebuilds_the_room(self):
        fid, data = self.to_furnish()
        first_design = data["design_id"]
        self.ca.post(f"{API}{fid}/back/")
        r = self.answer(fid, "style", "luxury")
        self.assertEqual(r.data["design_id"], first_design)          # same design, rebuilt
        self.assertEqual(r.data["rev"], 2)
        self.assertEqual(r.data["style"], "luxury")
        self.assertIn("items_reset", [w["code"] for w in r.data["warnings"]])
        self.assertEqual(Design.objects.filter(owner=self.a).count(), 1)

    def test_furniture_that_does_not_fit_is_reported_not_placed(self):
        fid = self.start()
        self.answer(fid, "goal", "living")
        self.answer(fid, "photo", {"skip": True})
        self.answer(fid, "elements", {"furniture": ["tv-unit"]})
        self.answer(fid, "size", {"width": 1000, "length": 1000, "height": 2400})
        r = self.answer(fid, "style", "modern")
        self.assertEqual(r.data["items"], [])
        self.assertEqual([w["code"] for w in r.data["warnings"]], ["not_placed"])


class OwnershipTests(Base):
    def test_other_user_gets_404_everywhere(self):
        fid, data = self.to_furnish()
        item = data["items"][0]["id"]
        rev = data["rev"]
        probes = [("get", f"{API}{fid}/", None), ("post", f"{API}{fid}/answer/", {"step": "furnish", "value": {"done": True}}), ("post", f"{API}{fid}/back/", None),
                  ("post", f"{API}{fid}/abandon/", None), ("get", f"{API}{fid}/model/", None), ("post", self.item_url(fid), {"template": "bedside", "rev": rev}),
                  ("patch", self.item_url(fid, item), {"x": 0, "rev": rev}), ("delete", self.item_url(fid, item) + f"?rev={rev}", None)]
        for method, url, body in probes:
            r = getattr(self.cb, method)(url, body, format="json") if body is not None else getattr(self.cb, method)(url)
            self.assertEqual(r.status_code, 404, (method, url, r.status_code))
        self.assertEqual(RoomFlow.objects.get(pk=fid).status, "active")
        self.assertEqual(len(Design.objects.get(pk=data["design_id"]).config["items"]), 2)

    def test_list_only_shows_own_flows(self):
        mine = self.start()
        theirs = self.start(self.cb)
        self.assertEqual([f["id"] for f in self.ca.get(API).data["results"]], [mine])
        self.assertEqual([f["id"] for f in self.cb.get(API).data["results"]], [theirs])

    def test_requires_authentication(self):
        anon = client_for()
        for method, url in (("get", API), ("post", API), ("get", f"{API}1/"), ("post", f"{API}1/answer/")):
            self.assertEqual(getattr(anon, method)(url).status_code, 401, url)

    def test_any_role_may_use_it(self):
        for u in (make_user("h@example.com", role="homeowner"), make_user("m@example.com", role="maker"), make_user("w@example.com", role="workshop")):
            self.assertEqual(client_for(u).post(API).status_code, 201, u.role)


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class PhotoTests(Base):
    def gallery_image(self, user):
        return GalleryImage.objects.create(owner=user, image=png(), name="mine", source="upload", width=40, height=30, size_bytes=10)

    def test_own_gallery_image_is_attached_and_follows_into_the_design(self):
        img = self.gallery_image(self.a)
        fid = self.start()
        self.answer(fid, "goal", "bedroom")
        r = self.answer(fid, "photo", {"image_id": img.id})
        self.assertEqual(r.data["photo_id"], img.id)
        self.answer(fid, "elements", {})
        self.answer(fid, "size", SIZE)
        r = self.answer(fid, "style", "modern")
        self.assertEqual(Design.objects.get(pk=r.data["design_id"]).room_image_id, img.id)

    def test_someone_elses_image_is_rejected_like_a_missing_one(self):
        theirs = self.gallery_image(self.b)
        fid = self.start()
        self.answer(fid, "goal", "bedroom")
        r1 = self.answer(fid, "photo", {"image_id": theirs.id}, expect=400)
        r2 = self.answer(fid, "photo", {"image_id": 999999}, expect=400)
        self.assertEqual(r1.data["error"]["fields"], r2.data["error"]["fields"])
        self.assertEqual(RoomFlow.objects.get(pk=fid).step, "photo")
        self.assertIsNone(RoomFlow.objects.get(pk=fid).photo)

    def test_photo_is_optional(self):
        fid = self.start()
        self.answer(fid, "goal", "bedroom")
        self.assertEqual(self.answer(fid, "photo", {"skip": True}).data["step"], "elements")

    def test_photo_is_not_analysed_or_changed(self):
        img = self.gallery_image(self.a)
        fid = self.start()
        self.answer(fid, "goal", "bedroom")
        self.answer(fid, "photo", {"image_id": img.id})
        img.refresh_from_db()
        self.assertEqual((img.width, img.height, img.name), (40, 30, "mine"))   # stored as it was uploaded; no analysis step exists


class ItemTests(Base):
    def setUp(self):
        super().setUp()
        self.fid, data = self.to_furnish(elements={"doors": 1, "windows": 1, "furniture": []})
        self.rev = data["rev"]

    def add(self, body, expect=201):
        r = self.ca.post(self.item_url(self.fid), {**body, "rev": self.rev}, format="json")
        self.assertEqual(r.status_code, expect, r.data)
        if r.status_code < 300:
            self.rev = r.data["rev"]
        return r

    def test_add_from_template_is_placed_automatically(self):
        r = self.add({"template": "wardrobe-2door"})
        item = r.data["item"]
        self.assertEqual((item["template"], item["width"], item["depth"], item["height"]), ("wardrobe-2door", 1000, 580, 2200))
        self.assertEqual(r.data["rev"], 2)
        self.assertEqual(len(r.data["items"]), 1)

    def test_add_with_explicit_position_and_size(self):
        r = self.add({"template": "bedside", "x": 100, "z": 100, "rot": 90, "width": 500, "height": 600})
        self.assertEqual((r.data["item"]["x"], r.data["item"]["rot"], r.data["item"]["width"]), (100, 90, 500))

    def test_position_outside_the_room_is_rejected(self):
        for pos in ({"x": -10, "z": 0}, {"x": 3900, "z": 0}, {"x": 0, "z": 2900}):
            r = self.add({"template": "wardrobe-2door", **pos}, expect=400)
            self.assertIn("position", r.data["error"]["fields"])

    def test_rotated_item_cannot_stick_out_of_the_corner(self):
        self.add({"template": "wardrobe-2door", "x": 3000, "z": 2400, "rot": 0, "doors": 2}, expect=201)  # 1000 x 580 footprint ends at 4000 x 2980
        r = self.add({"template": "wardrobe-2door", "x": 0, "z": 2400, "rot": 90}, expect=400)             # rotated: 580 x 1000 -> z1 = 3400
        self.assertIn("position", r.data["error"]["fields"])

    def test_overlap_is_rejected(self):
        self.add({"template": "wardrobe-2door", "x": 0, "z": 0})
        r = self.add({"template": "wardrobe-2door", "x": 500, "z": 100}, expect=400)
        self.assertIn("overlaps", r.data["error"]["fields"]["position"][0] if isinstance(r.data["error"]["fields"]["position"], list) else r.data["error"]["fields"]["position"])
        self.add({"template": "wardrobe-2door", "x": 1000, "z": 0})     # touching is fine

    def test_engine_rules_are_enforced(self):
        for bad in ({"width": 5000}, {"width": 100}, {"shelves": -1}, {"doors": 9}, {"depth": 1500}):
            self.add({"template": "wardrobe-2door", **bad}, expect=400)
        r = self.add({"template": "wardrobe-2door", "rot": 45}, expect=400)
        self.assertIn("rot", r.data["error"]["fields"])

    def test_item_taller_than_the_room_is_rejected(self):
        r = self.add({"template": "bedside", "height": 2800}, expect=400)
        self.assertIn("height", r.data["error"]["fields"])

    def test_unknown_template_and_missing_size(self):
        self.add({"template": "spaceship"}, expect=400)
        r = self.add({"name": "custom"}, expect=400)
        self.assertEqual(set(r.data["error"]["fields"]), {"width", "depth", "height"})

    def test_custom_item_without_template(self):
        r = self.add({"name": "Custom unit", "width": 700, "depth": 350, "height": 900, "shelves": 1, "doors": 1})
        self.assertEqual(r.data["item"]["name"], "Custom unit")

    def test_no_free_spot_is_a_clear_error(self):
        for z in (0, 1000, 2000):        # three 4000 x 1000 units fill the whole 4000 x 3000 room
            self.add({"template": "wardrobe-2door", "width": 4000, "depth": 1000, "height": 2200, "x": 0, "z": z})
        r = self.add({"template": "bedside"}, expect=400)
        self.assertIn("no free spot", str(r.data["error"]["fields"]["position"]))

    def test_move_rotate_resize_and_delete(self):
        item = self.add({"template": "wardrobe-2door", "x": 0, "z": 0}).data["item"]
        url = self.item_url(self.fid, item["id"])
        r = self.ca.patch(url, {"x": 1200, "z": 300, "rev": self.rev}, format="json")
        self.assertEqual((r.status_code, r.data["item"]["x"], r.data["item"]["z"]), (200, 1200, 300))
        self.rev = r.data["rev"]
        r = self.ca.patch(url, {"rot": 90, "rev": self.rev}, format="json")
        self.assertEqual((r.status_code, r.data["item"]["rot"]), (200, 90))
        self.rev = r.data["rev"]
        r = self.ca.patch(url, {"width": 1400, "height": 2000, "rev": self.rev}, format="json")
        self.assertEqual((r.status_code, r.data["item"]["width"], r.data["item"]["height"]), (200, 1400, 2000))
        self.rev = r.data["rev"]
        self.assertEqual(r.data["item"]["id"], item["id"])
        r = self.ca.delete(url + f"?rev={self.rev}")
        self.assertEqual((r.status_code, r.data["items"]), (200, []))

    def test_moving_out_of_the_room_or_into_another_item_is_rejected(self):
        a = self.add({"template": "wardrobe-2door", "x": 0, "z": 0}).data["item"]
        b = self.add({"template": "wardrobe-2door", "x": 1000, "z": 0}).data["item"]
        self.assertEqual(self.ca.patch(self.item_url(self.fid, b["id"]), {"x": 500, "rev": self.rev}, format="json").status_code, 400)
        self.assertEqual(self.ca.patch(self.item_url(self.fid, a["id"]), {"x": -5, "rev": self.rev}, format="json").status_code, 400)
        self.assertEqual(self.ca.patch(self.item_url(self.fid, a["id"]), {"rot": 33, "rev": self.rev}, format="json").status_code, 400)
        cfg = Design.objects.get(owner=self.a).config
        self.assertEqual((cfg["rev"], [i["x"] for i in cfg["items"]]), (self.rev, [0, 1000]))      # nothing changed

    def test_unknown_item_is_404(self):
        self.assertEqual(self.ca.patch(self.item_url(self.fid, "0" * 12), {"x": 1, "rev": self.rev}, format="json").status_code, 404)
        self.assertEqual(self.ca.delete(self.item_url(self.fid, "0" * 12) + f"?rev={self.rev}").status_code, 404)

    def test_stale_revision_is_409_and_changes_nothing(self):
        self.add({"template": "bedside"})
        stale = self.rev - 1
        r = self.ca.post(self.item_url(self.fid), {"template": "bedside", "rev": stale}, format="json")
        self.assertEqual((r.status_code, err_code(r), r.data["error"]["fields"]["current_rev"]), (409, "rev_conflict", self.rev))
        self.assertEqual(len(Design.objects.get(owner=self.a).config["items"]), 1)
        self.add({"template": "bedside"})   # with the current revision it works

    def test_two_clients_cannot_overwrite_each_other(self):
        item = self.add({"template": "wardrobe-2door", "x": 0, "z": 0}).data["item"]
        seen = self.rev                      # both clients loaded this revision
        url = self.item_url(self.fid, item["id"])
        self.assertEqual(self.ca.patch(url, {"x": 500, "rev": seen}, format="json").status_code, 200)
        r = self.ca.patch(url, {"x": 900, "rev": seen}, format="json")
        self.assertEqual((r.status_code, err_code(r)), (409, "rev_conflict"))
        self.assertEqual(Design.objects.get(owner=self.a).config["items"][0]["x"], 500)

    def test_revision_is_required_and_accepted_in_if_match(self):
        r = self.ca.post(self.item_url(self.fid), {"template": "bedside"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("rev", r.data["error"]["fields"])
        r = self.ca.post(self.item_url(self.fid), {"template": "bedside"}, format="json", HTTP_IF_MATCH=f'"{self.rev}"')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.ca.post(self.item_url(self.fid), {"template": "bedside"}, format="json", HTTP_IF_MATCH='"nope"').status_code, 400)

    def test_revision_increases_on_every_write(self):
        revs = [self.rev]
        item = self.add({"template": "bedside"}).data
        revs.append(item["rev"])
        r = self.ca.patch(self.item_url(self.fid, item["item"]["id"]), {"x": 700, "rev": item["rev"]}, format="json")
        revs.append(r.data["rev"])
        revs.append(self.ca.delete(self.item_url(self.fid, item["item"]["id"]) + f"?rev={r.data['rev']}").data["rev"])
        self.assertEqual(revs, [1, 2, 3, 4])

    def test_at_most_sixty_items(self):
        d = Design.objects.get(owner=self.a)
        d.config["items"] = [{"id": f"{i:012x}", "template": "", "name": "", "x": 0, "z": 0, "rot": 0, "width": 100, "depth": 100, "height": 100, "shelves": 0,
                              "doors": 0, "drawers": 0, "color": ""} for i in range(60)]
        d.save()
        r = self.add({"template": "bedside"}, expect=400)
        self.assertIn("items", r.data["error"]["fields"])

    def test_items_are_locked_while_the_user_is_back_at_an_earlier_step(self):
        self.ca.post(f"{API}{self.fid}/back/")        # furnish -> style
        r = self.ca.post(self.item_url(self.fid), {"template": "bedside", "rev": self.rev}, format="json")
        self.assertEqual((r.status_code, err_code(r), r.data["error"]["fields"]["expected"]), (409, "not_furnishing", "furnish"))

    def test_an_item_larger_than_the_room_is_reported_as_such(self):
        fid = self.start()
        for step, value in (("goal", "kitchen"), ("photo", {"skip": True}), ("elements", {}), ("size", {"width": 1000, "length": 1000, "height": 2400}), ("style", "modern")):
            rev = self.answer(fid, step, value).data["rev"]
        r = self.ca.post(self.item_url(fid), {"template": "wardrobe-2door", "width": 1500, "rev": rev}, format="json")   # valid cabinet, wider than the room
        self.assertEqual(r.status_code, 400)
        self.assertIn("larger than the room", str(r.data["error"]["fields"]["position"]))

    def test_items_need_the_furnish_step(self):
        fid = self.start()
        r = self.ca.post(self.item_url(fid), {"template": "bedside", "rev": 1}, format="json")
        self.assertEqual((r.status_code, err_code(r)), (409, "not_generated"))
        self.ca.post(f"{API}{fid}/abandon/")

    def test_door_zone_is_a_warning_in_the_response(self):
        r = self.add({"template": "wardrobe-2door", "x": 1000, "z": 0, "rot": 0})   # door on the north wall at x 1000..1900
        self.assertEqual([w["code"] for w in r.data["warnings"]], ["door_zone"])

    def test_model_follows_the_edits(self):
        self.add({"template": "wardrobe-2door", "x": 0, "z": 0})
        m = self.ca.get(f"{API}{self.fid}/model/").data
        self.assertEqual(m["rev"], self.rev)
        self.assertTrue(any(b.get("item") for b in m["boxes"]))
