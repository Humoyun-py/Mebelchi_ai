import copy

from django.test import SimpleTestCase

from apps.conversations import flow
from apps.geometry import room as geo

CTX = flow.FlowContext(templates=[
    {"slug": "base-cabinet", "category": "kitchen", "name": "Base cabinet", "defaults": {"width": 600, "height": 720, "depth": 560}},
    {"slug": "wardrobe-2door", "category": "wardrobe", "name": "Two-door wardrobe", "defaults": {"width": 1000, "height": 2200, "depth": 580}},
    {"slug": "bedside", "category": "bedroom", "name": "Bedside table", "defaults": {"width": 450, "height": 500, "depth": 400}},
    {"slug": "tv-unit", "category": "tv_unit", "name": "TV unit", "defaults": {"width": 1800, "height": 450, "depth": 400}},
])
SIZE = {"width": 4000, "length": 3000, "height": 2700}
DOOR = {"type": "door", "wall": "north", "offset": 1000, "width": 900, "height": 2100, "sill": 0}
WINDOW = {"type": "window", "wall": "east", "offset": 800, "width": 1200, "height": 1200, "sill": 900}


def run(state, *answers):
    for step, value in answers:
        state = flow.apply_answer(state, step, value, CTX)
    return state


def to_style(goal="bedroom", doors=1, windows=1, furniture=("bedside",)):
    ops = ([DOOR] if doors else []) + ([WINDOW] if windows else [])
    steps = [("goal", goal), ("photo", {"skip": True}), ("elements", {"doors": doors, "windows": windows, "furniture": list(furniture)}), ("size", SIZE)]
    if doors + windows:
        steps.append(("openings", ops))
    return run(flow.initial(), *steps)


class DescriptorTests(SimpleTestCase):
    def test_every_step_has_texts_in_three_languages(self):
        for step in flow.STEPS:
            d = flow.describe({"step": step, "answers": {"size": SIZE, "elements": {"doors": 1, "windows": 0, "furniture": []}}}, CTX)
            for key in ("title", "prompt"):
                self.assertEqual(set(d[key]), {"en", "uz", "ru"}, (step, key))
                if step != "generate":
                    self.assertTrue(all(d[key].values()), (step, key))

    def test_kinds(self):
        kinds = {s: flow.describe({"step": s, "answers": {"size": SIZE, "elements": {"doors": 1, "windows": 0}}}, CTX)["kind"] for s in flow.STEPS}
        self.assertEqual(kinds, {"goal": "choice", "photo": "photo", "elements": "number_group", "size": "number_group", "openings": "openings",
                                 "style": "choice", "generate": "summary", "furnish": "furnish", "done": "summary"})

    def test_goal_options(self):
        d = flow.describe(flow.initial(), CTX)
        self.assertEqual([o["id"] for o in d["options"]], ["kitchen", "bedroom", "living", "wardrobe", "office", "other"])
        self.assertFalse(d["can_back"])
        self.assertEqual((d["index"], d["total"]), (1, 7))

    def test_size_fields_carry_the_limits(self):
        d = flow.describe({"step": "size", "answers": {}}, CTX)
        self.assertEqual({f["key"]: (f["min"], f["max"]) for f in d["fields"]}, {"width": (1000, 15000), "length": (1000, 15000), "height": (2000, 4500)})

    def test_furniture_options_follow_the_room_type(self):
        opts = lambda goal: {o["id"] for o in next(f for f in flow.describe({"step": "elements", "answers": {"goal": goal}}, CTX)["fields"] if f["key"] == "furniture")["options"]}
        self.assertEqual(opts("kitchen"), {"base-cabinet"})
        self.assertEqual(opts("bedroom"), {"bedside", "wardrobe-2door"})
        self.assertEqual(opts("living"), {"tv-unit"})
        self.assertEqual(opts("other"), {"base-cabinet", "wardrobe-2door", "bedside", "tv-unit"})

    def test_openings_descriptor_states_what_is_required(self):
        s = to_style(doors=1, windows=1)
        s2 = flow.back(s)  # back from style -> openings
        d = flow.describe(s2, CTX)
        self.assertEqual(d["step"], "openings")
        self.assertEqual(d["required"], {"doors": 1, "windows": 1})
        self.assertEqual(d["wall_lengths"], {"north": 4000, "east": 3000, "south": 4000, "west": 3000})
        self.assertEqual([(o["type"], o["wall"], o["offset"]) for o in d["value"]], [("door", "north", 1000), ("window", "east", 800)])

    def test_returning_user_gets_previous_value_for_prefill(self):
        s = to_style()
        size_state = {**s, "step": "size"}
        self.assertEqual(flow.describe(size_state, CTX)["value"], SIZE)


class TransitionTests(SimpleTestCase):
    def test_full_path(self):
        s = to_style()
        self.assertEqual(s["step"], "style")
        s = flow.apply_answer(s, "style", "modern", CTX)
        self.assertEqual(s["step"], "generate")
        s = flow.to_furnish(s)
        self.assertEqual(s["step"], "furnish")
        s = flow.apply_answer(s, "furnish", {"done": True}, CTX)
        self.assertEqual(s["step"], "done")
        a = s["answers"]
        self.assertEqual((a["goal"], a["style"], a["size"]), ("bedroom", "modern", SIZE))
        self.assertEqual(a["photo"], {"skipped": True})
        self.assertEqual(len(a["openings"]), 2)

    def test_openings_step_is_skipped_without_doors_and_windows(self):
        s = to_style(doors=0, windows=0)
        self.assertEqual(s["step"], "style")
        self.assertEqual(s["answers"]["openings"], [])
        self.assertEqual(flow.back(s)["step"], "size")

    def test_answer_to_the_wrong_step_is_a_mismatch(self):
        with self.assertRaises(flow.StepMismatch) as cm:
            flow.apply_answer(flow.initial(), "size", SIZE, CTX)
        self.assertEqual((cm.exception.expected, cm.exception.got), ("goal", "size"))
        s = run(flow.initial(), ("goal", "kitchen"))
        with self.assertRaises(flow.StepMismatch):
            flow.apply_answer(s, "goal", "office", CTX)   # already moved on

    def test_automatic_steps_cannot_be_answered(self):
        for step in ("generate", "done"):
            with self.assertRaises(flow.FlowError):
                flow.apply_answer({"step": step, "answers": {}}, step, "x", CTX)

    def test_input_state_is_not_mutated(self):
        s = flow.initial()
        before = copy.deepcopy(s)
        flow.apply_answer(s, "goal", "kitchen", CTX)
        self.assertEqual(s, before)


class ValidationTests(SimpleTestCase):
    def fails(self, state, step, value):
        with self.assertRaises(flow.FlowValidationError) as cm:
            flow.apply_answer(state, step, value, CTX)
        return cm.exception.errors

    def test_goal(self):
        for bad in ("garage", "", None, 1, ["kitchen"]):
            self.assertIn("value", self.fails(flow.initial(), "goal", bad))

    def test_photo(self):
        s = run(flow.initial(), ("goal", "kitchen"))
        for bad in ("skip", {}, {"image_id": 0}, {"image_id": -3}, {"image_id": "7"}, {"image_id": True}, {"skip": "yes"}, None):
            self.fails(s, "photo", bad)
        self.assertEqual(flow.apply_answer(s, "photo", {"image_id": 7}, CTX)["answers"]["photo"], {"image_id": 7})
        self.assertEqual(flow.apply_answer(s, "photo", {"skip": True}, CTX)["answers"]["photo"], {"skipped": True})

    def elements_state(self, goal="bedroom"):
        return run(flow.initial(), ("goal", goal), ("photo", {"skip": True}))

    def test_elements_counts_and_furniture(self):
        s = self.elements_state()
        for bad, key in (({"doors": 3}, "doors"), ({"doors": -1}, "doors"), ({"windows": 5}, "windows"), ({"doors": 1.5}, "doors"), ({"doors": True}, "doors"),
                         ({"furniture": "bedside"}, "furniture"), ({"furniture": ["base-cabinet"]}, "furniture"), ({"furniture": ["nope"]}, "furniture"),
                         ({"furniture": ["bedside"] * 61}, "furniture")):
            self.assertIn(key, self.fails(s, "elements", bad), bad)
        self.assertIn("value", self.fails(s, "elements", [1]))
        ok = flow.apply_answer(s, "elements", {"doors": 2, "windows": 4, "furniture": ["bedside", "bedside", "wardrobe-2door"]}, CTX)
        self.assertEqual(ok["step"], "size")

    def test_elements_defaults_to_nothing(self):
        s = flow.apply_answer(self.elements_state(), "elements", {}, CTX)
        self.assertEqual(s["answers"]["elements"], {"doors": 0, "windows": 0, "furniture": []})

    def test_size_limits(self):
        s = run(flow.initial(), ("goal", "kitchen"), ("photo", {"skip": True}), ("elements", {}))
        for bad in ({**SIZE, "width": 999}, {**SIZE, "length": 15001}, {**SIZE, "height": 1999}, {**SIZE, "height": 4501}, {"width": 3000}, "big"):
            self.assertTrue(self.fails(s, "size", bad), bad)

    def test_openings_must_match_the_requested_counts(self):
        s = run(flow.initial(), ("goal", "kitchen"), ("photo", {"skip": True}), ("elements", {"doors": 1, "windows": 1}), ("size", SIZE))
        self.assertIn("openings", self.fails(s, "openings", [DOOR]))
        self.assertIn("openings", self.fails(s, "openings", [DOOR, DOOR]))
        self.assertIn("openings", self.fails(s, "openings", []))
        self.assertTrue(self.fails(s, "openings", [{**DOOR, "offset": 3500}, WINDOW]))      # door does not fit the wall
        self.assertTrue(self.fails(s, "openings", "north"))

    def test_openings_overlap_is_rejected_here_too(self):
        s = run(flow.initial(), ("goal", "kitchen"), ("photo", {"skip": True}), ("elements", {"doors": 1, "windows": 1}), ("size", SIZE))
        bad = [DOOR, {**WINDOW, "wall": "north", "offset": 1500, "sill": 900}]
        self.assertIn("openings", self.fails(s, "openings", bad))

    def test_style(self):
        s = to_style()
        for bad in ("gothic", None, 3):
            self.assertIn("value", self.fails(s, "style", bad))
        for ok in ("modern", "classic", "minimal", "luxury"):
            self.assertEqual(flow.apply_answer(s, "style", ok, CTX)["step"], "generate")

    def test_failed_answer_leaves_state_unchanged(self):
        s = to_style()
        before = copy.deepcopy(s)
        with self.assertRaises(flow.FlowValidationError):
            flow.apply_answer(s, "style", "gothic", CTX)
        self.assertEqual(s, before)


class BackAndInvalidationTests(SimpleTestCase):
    def test_back_walks_through_the_steps_and_keeps_answers(self):
        s = to_style()
        trail = []
        while s["step"] != "photo":
            s = flow.back(s)
            trail.append(s["step"])
        self.assertEqual(trail, ["openings", "size", "elements", "photo"])
        self.assertEqual(s["answers"]["size"], SIZE)
        self.assertEqual(flow.back(s)["step"], "goal")
        with self.assertRaises(flow.FlowError):
            flow.back(flow.initial())

    def test_cannot_go_back_from_automatic_or_finished_steps(self):
        for step in ("generate", "done"):
            with self.assertRaises(flow.FlowError):
                flow.back({"step": step, "answers": {}})

    def test_furnish_goes_back_to_style(self):
        s = flow.to_furnish(flow.apply_answer(to_style(), "style", "modern", CTX))
        self.assertEqual(flow.back(s)["step"], "style")

    def test_new_size_discards_openings_only(self):
        s = to_style()
        s = flow.back(flow.back(s))                                    # at size
        self.assertEqual(s["step"], "size")
        s = flow.apply_answer(s, "size", {**SIZE, "width": 5000}, CTX)
        self.assertEqual(s["step"], "openings")
        self.assertNotIn("openings", s["answers"])
        self.assertEqual(s["answers"]["elements"]["doors"], 1)         # kept
        self.assertEqual(s["answers"]["goal"], "bedroom")

    def test_new_door_count_discards_openings(self):
        s = flow.back(flow.back(flow.back(to_style())))                # at elements
        self.assertEqual(s["step"], "elements")
        s = flow.apply_answer(s, "elements", {"doors": 0, "windows": 0, "furniture": []}, CTX)
        self.assertEqual(s["step"], "size")
        self.assertEqual(s["answers"]["size"], SIZE)

    def test_changing_the_goal_clears_elements_and_openings(self):
        s = to_style()
        s = {**s, "step": "goal"}
        s = flow.apply_answer(s, "goal", "kitchen", CTX)
        self.assertNotIn("elements", s["answers"])
        self.assertNotIn("openings", s["answers"])
        self.assertEqual(s["answers"]["size"], SIZE)
        self.assertEqual(s["step"], "photo")

    def test_independent_steps_do_not_cost_other_answers(self):
        s = to_style()
        photo = flow.apply_answer({**s, "step": "photo"}, "photo", {"image_id": 5}, CTX)
        for key in ("goal", "elements", "size", "openings"):
            self.assertIn(key, photo["answers"], key)
        styled = flow.apply_answer(flow.apply_answer(s, "style", "luxury", CTX) | {"step": "style"}, "style", "classic", CTX)
        self.assertEqual(styled["answers"]["style"], "classic")
        self.assertIn("openings", styled["answers"])

    def test_resume_gives_the_same_question(self):
        s = to_style()
        stored = {"step": s["step"], "answers": copy.deepcopy(s["answers"])}      # what the database holds
        self.assertEqual(flow.describe(stored, CTX), flow.describe(s, CTX))
        self.assertEqual(flow.apply_answer(stored, "style", "modern", CTX)["step"], "generate")
