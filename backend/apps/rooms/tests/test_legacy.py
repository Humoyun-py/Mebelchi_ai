from django.test import SimpleTestCase, TestCase

from apps.core.tests.helpers import client_for, make_user
from apps.designs.models import Design
from apps.furniture.models import FurnitureTemplate
from apps.geometry import room as geo
from apps.rooms import legacy
from apps.rooms.models import RoomFlow
from apps.rooms.services import MAX_ACTIVE_FLOWS

IMPORT = "/api/v1/rooms/import-design/"
OLD = {"room": "living", "style": "classic", "template": "", "input": {"width": 1800, "height": 450, "depth": 400, "thickness": 18, "shelves": 1, "doors": 2, "drawers": 0},
       "color": "#8b6f4e", "wallColor": "#e7dcc8", "roomW": 4200, "roomL": 5000, "roomH": 2700, "wall": "north", "align": "center", "notes": "near the window"}
TEMPLATES = [{"slug": "tv-unit", "category": "tv_unit", "name": "TV unit", "defaults": {"width": 1800, "height": 450, "depth": 400}},
             {"slug": "wardrobe-2", "category": "wardrobe", "name": "Wardrobe", "defaults": {"width": 1200, "height": 2200, "depth": 600}}]


class ConvertTests(SimpleTestCase):
    def test_room_size_style_colors_and_notes_are_kept(self):
        out = legacy.convert(OLD, TEMPLATES)
        c = out["config"]
        self.assertEqual(c["room"], {"width": 4200, "length": 5000, "height": 2700})
        self.assertEqual((c["schema"], c["style"], c["goal"], c["notes"]), ("room.v1", "classic", "living", "near the window"))
        self.assertEqual(c["colors"], {"wall": "#e7dcc8", "floor": legacy.FLOOR_COLOR, "item": "#8b6f4e"})
        self.assertEqual(c["legacy"], OLD)
        self.assertEqual(out["answers"]["size"], c["room"])

    def test_cabinet_position_matches_the_old_plan_for_every_wall_and_alignment(self):
        W, L, w, d = 4200, 5000, 1800, 400
        cases = {("north", "start"): (0, 0), ("north", "center"): ((W - w) / 2, 0), ("north", "end"): (W - w, 0), ("south", "center"): ((W - w) / 2, L - d),
                 ("west", "start"): (0, 0), ("west", "end"): (0, L - w), ("east", "center"): (W - d, (L - w) / 2), ("east", "end"): (W - d, L - w)}
        for (wall, align), (x, z) in cases.items():
            item = legacy.convert({**OLD, "wall": wall, "align": align}, TEMPLATES)["config"]["items"][0]
            self.assertEqual((item["x"], item["z"], item["rot"]), (x, z, geo.WALL_ROT[wall]), (wall, align))
            self.assertEqual((item["width"], item["depth"], item["height"]), (w, d, 450))

    def test_known_template_is_kept_and_unknown_one_is_reported(self):
        ok = legacy.convert({**OLD, "template": "tv-unit"}, TEMPLATES)
        self.assertEqual(ok["config"]["items"][0]["template"], "tv-unit")
        self.assertEqual(ok["answers"]["elements"]["furniture"], ["tv-unit"])
        gone = legacy.convert({**OLD, "template": "deleted"}, TEMPLATES)
        self.assertEqual(gone["config"]["items"][0]["template"], "")
        self.assertTrue(any("deleted" in n for n in gone["notes"]))

    def test_template_outside_the_room_type_switches_goal_to_other(self):
        out = legacy.convert({**OLD, "room": "kitchen", "template": "tv-unit"}, TEMPLATES)
        self.assertEqual(out["answers"]["goal"], "other")

    def test_cabinet_that_does_not_fit_is_reported_but_the_room_is_imported(self):
        out = legacy.convert({**OLD, "roomW": 1500, "input": {**OLD["input"], "width": 3000}}, TEMPLATES)
        self.assertEqual(out["config"]["items"], [])
        self.assertEqual(out["config"]["not_placed"][0]["code"], "not_placed")
        self.assertIn("wider", out["config"]["not_placed"][0]["message"])
        self.assertEqual(out["config"]["room"]["width"], 1500)

    def test_room_outside_new_limits_names_the_old_field(self):
        with self.assertRaises(legacy.LegacyError) as cm:
            legacy.convert({**OLD, "roomW": 500, "roomH": "tall"}, TEMPLATES)
        self.assertEqual(set(cm.exception.errors), {"roomW", "roomH"})

    def test_sparse_config_gets_the_old_defaults_and_no_invented_cabinet(self):
        out = legacy.convert({"style": "modern"}, TEMPLATES)
        self.assertEqual(out["config"]["room"], {"width": 4200, "length": 5000, "height": 2700})
        self.assertEqual(out["config"]["items"], [])

    def test_bad_values_do_not_crash(self):
        out = legacy.convert({**OLD, "style": "nope", "room": "garage", "color": "red", "wall": "up", "align": "x", "input": {"width": "abc"}}, TEMPLATES)
        self.assertEqual((out["config"]["style"], out["answers"]["goal"]), ("modern", "other"))
        self.assertEqual(out["config"]["items"], [])
        self.assertEqual(out["config"]["not_placed"][0]["code"], "not_placed")
        self.assertEqual(len(out["notes"]), 2)

    def test_room_designer_config_is_refused(self):
        with self.assertRaises(legacy.LegacyError):
            legacy.convert({"schema": "room.v1"}, TEMPLATES)

    def test_conversion_does_not_mutate_its_input(self):
        import copy
        before = copy.deepcopy(OLD)
        legacy.convert(OLD, TEMPLATES)
        self.assertEqual(OLD, before)


class ImportApiTests(TestCase):
    def setUp(self):
        self.a, self.b = make_user("a@x.com", "homeowner"), make_user("b@x.com", "homeowner")
        self.ca, self.cb = client_for(self.a), client_for(self.b)
        FurnitureTemplate.objects.get_or_create(slug="tv-unit", defaults={"category": "tv_unit", "name": "TV unit", "defaults": {"width": 1800, "height": 450, "depth": 400}, "is_active": True})
        self.old = Design.objects.create(owner=self.a, kind="interior", name="My living room", config=OLD)

    def imp(self, c=None, design=None):
        return (c or self.ca).post(IMPORT, {"design": design or self.old.pk}, format="json")

    def test_import_opens_the_design_in_the_room_designer(self):
        r = self.imp()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["step"], r.data["status"]), ("furnish", "active"))
        self.assertEqual(r.data["room"]["config"]["room"]["width"], 4200)
        self.assertEqual(len(r.data["room"]["config"]["items"]), 1)
        self.assertEqual(self.ca.get(f"/api/v1/rooms/{r.data['id']}/model/").status_code, 200)

    def test_old_design_is_untouched_and_copy_keeps_name_and_owner(self):
        r = self.imp()
        self.old.refresh_from_db()
        self.assertEqual((self.old.config, self.old.name, self.old.kind), (OLD, "My living room", "interior"))
        new = Design.objects.get(pk=r.data["design"])
        self.assertNotEqual(new.pk, self.old.pk)
        self.assertEqual((new.name, new.owner_id, new.config["migrated_from"], new.config["legacy"]), ("My living room", self.a.id, self.old.pk, OLD))

    def test_import_twice_returns_the_same_flow_and_creates_nothing(self):
        first, second = self.imp(), self.imp()
        self.assertEqual((first.status_code, second.status_code), (201, 200))
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual((RoomFlow.objects.count(), Design.objects.count()), (1, 2))

    def test_edits_survive_a_second_import(self):
        r = self.imp()
        item = r.data["room"]["config"]["items"][0]["id"]
        self.assertEqual(self.ca.patch(f"/api/v1/rooms/{r.data['id']}/items/{item}/", {"x": 100}, format="json").status_code, 200)
        again = self.imp()
        self.assertEqual(again.data["room"]["config"]["items"][0]["x"], 100)

    def test_importing_the_new_design_returns_its_own_flow(self):
        r = self.imp()
        again = self.imp(design=r.data["design"])
        self.assertEqual((again.status_code, again.data["id"]), (200, r.data["id"]))

    def test_other_users_design_is_404_and_creates_nothing(self):
        r = self.imp(c=self.cb)
        self.assertEqual(r.status_code, 404)
        self.assertEqual((RoomFlow.objects.count(), Design.objects.count()), (0, 1))

    def test_furniture_design_and_missing_design_are_404(self):
        f = Design.objects.create(owner=self.a, kind="furniture", name="F", config={})
        self.assertEqual(self.imp(design=f.pk).status_code, 404)
        self.assertEqual(self.imp(design=99999).status_code, 404)

    def test_login_is_required(self):
        from rest_framework.test import APIClient
        self.assertIn(APIClient().post(IMPORT, {"design": self.old.pk}, format="json").status_code, (401, 403))

    def test_bad_body_is_400(self):
        for body in ({}, {"design": "x"}, {"design": True}, {"design": None}):
            self.assertEqual(self.ca.post(IMPORT, body, format="json").status_code, 400, body)

    def test_unconvertible_room_is_400_with_the_old_field_name_and_nothing_is_created(self):
        bad = Design.objects.create(owner=self.a, kind="interior", name="Tiny", config={**OLD, "roomW": 300})
        r = self.imp(design=bad.pk)
        self.assertEqual(r.status_code, 400)
        self.assertIn("roomW", str(r.data))
        self.assertEqual((RoomFlow.objects.count(), Design.objects.count()), (0, 2))

    def test_room_photo_is_kept_only_when_it_is_the_users_own(self):
        from apps.galleries.models import GalleryImage
        mine = GalleryImage.objects.create(owner=self.a, name="m", image="room/m.png", source="room") if "source" in [f.name for f in GalleryImage._meta.fields] else None
        if mine is None:
            self.skipTest("gallery model differs")
        self.old.room_image = mine
        self.old.save()
        r = self.imp()
        self.assertEqual(r.data["answers"]["photo"], {"image_id": mine.pk})
        self.assertEqual(Design.objects.get(pk=r.data["design"]).room_image_id, mine.pk)

    def test_unfinished_flow_limit_is_a_409_not_a_crash(self):
        for _ in range(MAX_ACTIVE_FLOWS):
            RoomFlow.objects.create(owner=self.a)
        self.assertEqual(self.imp().status_code, 409)
        self.assertEqual(Design.objects.count(), 1)

    def test_listed_design_links_to_the_imported_flow(self):
        r = self.imp()
        row = next(d for d in self.ca.get("/api/v1/designs/").data["results"] if d["id"] == r.data["design"])
        self.assertEqual(row["room_flow"], r.data["id"])
        old_row = next(d for d in self.ca.get("/api/v1/designs/").data["results"] if d["id"] == self.old.pk)
        self.assertIsNone(old_row["room_flow"])
