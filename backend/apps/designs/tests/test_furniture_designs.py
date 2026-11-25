from django.test import TestCase

from apps.audit.models import AuditLog
from apps.core.tests.helpers import client_for, make_user

D = "/api/v1/designs/"
INPUT = dict(width=900, height=2000, depth=500, thickness=18, shelves=2, doors=2, drawers=2)
CONFIG = {"schema_version": 1, "input": dict(INPUT, cabinet_type="standard", handle_style="knob"), "color": "#c9a27a", "colors": {"fronts": "#445566"}, "material": None}


class FurnitureDesignValidationTests(TestCase):
    def setUp(self):
        self.a, self.b = make_user("a@x.com"), make_user("b@x.com")
        self.ca, self.cb = client_for(self.a), client_for(self.b)

    def post(self, config, **kw):
        return self.ca.post(D, {"name": "Wardrobe", "kind": "furniture", "config": config, **kw}, format="json")

    def test_a_full_editor_config_round_trips(self):
        r = self.post(CONFIG)
        self.assertEqual(r.status_code, 201, r.data)
        got = self.ca.get(f"{D}{r.data['id']}/").data["config"]
        self.assertEqual(got, CONFIG)

    def test_old_seven_number_configs_still_save(self):
        r = self.post({"input": INPUT, "color": "#c9a27a"})
        self.assertEqual(r.status_code, 201, r.data)

    def test_an_impossible_cabinet_is_refused_with_the_reason(self):
        r = self.post({"input": dict(INPUT, width=50)})
        self.assertEqual(r.status_code, 400)
        self.assertIn("width", r.data["error"]["fields"]["config"][0])
        r = self.post({"input": dict(INPUT, cabinet_type="sliding_wardrobe", doors=1, drawers=0)})
        self.assertEqual(r.status_code, 400); self.assertIn("doors", str(r.data))

    def test_bad_colours_styles_and_versions_are_refused(self):
        for bad in ({"input": INPUT, "color": "red"}, {"input": INPUT, "colors": {"fronts": "blue"}}, {"input": INPUT, "colors": {"doors": "#112233"}},
                    {"input": dict(INPUT, handle_style="gold")}, {"input": INPUT, "schema_version": 99}, {"input": INPUT, "schema_version": "1"},
                    {"input": "nope"}, {"input": {"width": 800}}):
            self.assertEqual(self.post(bad).status_code, 400, bad)

    def test_other_kinds_and_partial_updates_are_not_affected(self):
        self.assertEqual(self.ca.post(D, {"name": "Room", "kind": "interior", "config": {"style": "modern", "anything": [1, 2]}}, format="json").status_code, 201)
        did = self.post(CONFIG).data["id"]
        self.assertEqual(self.ca.patch(f"{D}{did}/", {"name": "Renamed"}, format="json").status_code, 200)       # no config: nothing to validate
        r = self.ca.patch(f"{D}{did}/", {"config": {"input": dict(INPUT, width=10)}}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.ca.get(f"{D}{did}/").data["config"]["input"]["width"], 900)                         # the bad update changed nothing


class DesignModelEndpointTests(TestCase):
    def setUp(self):
        self.a, self.b = make_user("a@x.com"), make_user("b@x.com")
        self.ca, self.cb = client_for(self.a), client_for(self.b)
        self.did = self.ca.post(D, {"name": "Wardrobe", "kind": "furniture", "config": CONFIG}, format="json").data["id"]

    def test_the_model_is_rebuilt_from_the_saved_config_and_proves_itself(self):
        r = self.ca.get(f"{D}{self.did}/model/")
        self.assertEqual(r.status_code, 200, r.data)
        g, c = r.data["geometry"], r.data["calculation"]
        self.assertTrue(g["consistency"]["valid"])
        self.assertEqual(g["dimensions"]["width"], 900)
        self.assertEqual({b["color"] for b in g["boxes"] if b["kind"] == "door"}, {"#445566"})       # the saved colour group survives
        self.assertTrue(all(b["sx"] == 24 for b in g["boxes"] if "handle" in b["name"].lower()))   # knob style survives
        self.assertEqual(sum(1 for b in g["boxes"] if b["kind"] == "door"), 2)
        self.assertEqual(c["summary"]["panel_count"], sum(p["quantity"] for p in c["parts"]))
        self.assertIn("Handle", {h["name"] for h in c["hardware"]})

    def test_it_is_private_and_only_for_furniture(self):
        self.assertEqual(self.cb.get(f"{D}{self.did}/model/").status_code, 404)
        self.assertEqual(client_for().get(f"{D}{self.did}/model/").status_code, 401)
        room = self.ca.post(D, {"name": "Room", "kind": "interior", "config": {"style": "x"}}, format="json").data["id"]
        self.assertEqual(self.ca.get(f"{D}{room}/model/").status_code, 400)

    def test_a_design_that_no_longer_validates_explains_itself(self):
        from apps.designs.models import Design
        Design.objects.filter(pk=self.did).update(config={"input": dict(INPUT, shelves=20, height=500)})   # stored before a rule existed
        r = self.ca.get(f"{D}{self.did}/model/")
        self.assertEqual(r.status_code, 400)
        self.assertIn("no longer passes validation", r.data["error"]["detail"])


class DesignDuplicateTests(TestCase):
    def setUp(self):
        self.a, self.b = make_user("a@x.com"), make_user("b@x.com")
        self.ca, self.cb = client_for(self.a), client_for(self.b)
        self.did = self.ca.post(D, {"name": "Wardrobe", "kind": "furniture", "config": CONFIG}, format="json").data["id"]

    def test_duplicate_is_an_independent_copy(self):
        r = self.ca.post(f"{D}{self.did}/duplicate/")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["name"], r.data["config"]), ("Wardrobe (copy)", CONFIG))
        self.assertNotEqual(r.data["id"], self.did)
        self.ca.patch(f"{D}{r.data['id']}/", {"config": dict(CONFIG, color="#000000")}, format="json")
        self.assertEqual(self.ca.get(f"{D}{self.did}/").data["config"]["color"], "#c9a27a")

    def test_only_the_owner_can_duplicate_and_it_is_audited(self):
        self.assertEqual(self.cb.post(f"{D}{self.did}/duplicate/").status_code, 404)
        new = self.ca.post(f"{D}{self.did}/duplicate/").data["id"]
        e = AuditLog.objects.get(model="designs.design", object_id=str(new), action="create")
        self.assertEqual((e.actor, e.object_repr), (self.a, "Wardrobe (copy)"))
        self.assertEqual(self.ca.get(D).data["count"], 2)
