from django.test import SimpleTestCase

from apps.geometry import room as geo

ROOM = {"width": 4000, "length": 3000, "height": 2700}


def cab(**kw):
    return {"x": 0, "z": 0, "rot": 0, "width": 800, "depth": 400, "height": 2000, "shelves": 3, "doors": 2, "drawers": 0, **kw}


def door(**kw):
    return {"type": "door", "wall": "north", "offset": 1000, "width": 900, "height": 2100, "sill": 0, **kw}


def window(**kw):
    return {"type": "window", "wall": "east", "offset": 800, "width": 1200, "height": 1200, "sill": 900, **kw}


class RoomLimitTests(SimpleTestCase):
    def test_accepts_boundaries(self):
        self.assertEqual(geo.validate_room({"width": 1000, "length": 15000, "height": 2000}), {"width": 1000, "length": 15000, "height": 2000})
        geo.validate_room({"width": 15000, "length": 1000, "height": 4500})

    def test_rejects_out_of_range_and_bad_types(self):
        for bad in ({"width": 999}, {"width": 15001}, {"length": 500}, {"height": 1999}, {"height": 4501}, {"width": "4000"}, {"width": True}, {"width": None}):
            with self.assertRaises(geo.RoomError, msg=bad) as cm:
                geo.validate_room({**ROOM, **bad})
            self.assertIn(next(iter(bad)), cm.exception.errors)

    def test_missing_fields_and_non_object(self):
        with self.assertRaises(geo.RoomError) as cm:
            geo.validate_room({})
        self.assertEqual(set(cm.exception.errors), {"width", "length", "height"})
        with self.assertRaises(geo.RoomError):
            geo.validate_room([])

    def test_cabinet_depth_limit_is_not_used_for_rooms(self):
        geo.validate_room({"width": 4000, "length": 5000, "height": 2700})  # 5000 mm deep would fail the cabinet LIMITS (depth <= 1000)


class OpeningTests(SimpleTestCase):
    def test_valid_door_and_window(self):
        d = geo.validate_opening(door(), ROOM)
        self.assertEqual((d["type"], d["sill"]), ("door", 0))
        self.assertTrue(d["id"])
        self.assertEqual(geo.validate_opening(window(), ROOM)["sill"], 900)

    def test_door_wider_than_wall_is_rejected(self):
        with self.assertRaises(geo.RoomError) as cm:
            geo.validate_opening(door(offset=3100, width=900), ROOM)  # ends at 4000, the 100 mm margin is gone
        self.assertIn("offset", cm.exception.errors)
        with self.assertRaises(geo.RoomError):
            geo.validate_opening(door(wall="west", offset=2200, width=900), ROOM)  # west wall is only 3000 long

    def test_margin_from_wall_end(self):
        geo.validate_opening(door(offset=100), ROOM)
        with self.assertRaises(geo.RoomError):
            geo.validate_opening(door(offset=99), ROOM)
        geo.validate_opening(door(offset=3000, width=900), ROOM)  # ends exactly 100 mm before the wall end
        with self.assertRaises(geo.RoomError):
            geo.validate_opening(door(offset=3001, width=900), ROOM)

    def test_window_above_ceiling_is_rejected(self):
        with self.assertRaises(geo.RoomError) as cm:
            geo.validate_opening(window(sill=1500, height=1200), ROOM)  # top at 2700 = ceiling, margin is 100
        self.assertIn("height", cm.exception.errors)
        geo.validate_opening(window(sill=1400, height=1200), ROOM)  # top at 2600: exactly the margin

    def test_door_must_start_at_the_floor(self):
        with self.assertRaises(geo.RoomError) as cm:
            geo.validate_opening(door(sill=100), ROOM)
        self.assertIn("sill", cm.exception.errors)

    def test_type_wall_and_size_limits(self):
        for bad in ({"type": "gate"}, {"wall": "up"}, {"width": 599}, {"width": 1201}, {"height": 1799}, {"height": 2401}, {"offset": "1"}):
            with self.assertRaises(geo.RoomError, msg=bad):
                geo.validate_opening(door(**bad), ROOM)
        for bad in ({"width": 299}, {"width": 3001}, {"height": 299}, {"height": 2401}, {"sill": -1}, {"sill": 1501}):
            with self.assertRaises(geo.RoomError, msg=bad):
                geo.validate_opening(window(**bad), ROOM)

    def test_overlapping_openings_are_rejected_and_the_gap_is_exact(self):
        with self.assertRaises(geo.RoomError) as cm:
            geo.validate_openings([door(offset=1000), window(wall="north", offset=1800, sill=900)], ROOM)
        self.assertIn("openings", cm.exception.errors)
        # door ends at 1900; a window starting at 2000 leaves exactly the 100 mm gap
        self.assertEqual(len(geo.validate_openings([door(offset=1000), window(wall="north", offset=2000, sill=900)], ROOM)), 2)

    def test_same_offset_on_different_walls_is_fine(self):
        geo.validate_openings([door(wall="north"), door(wall="south")], ROOM)

    def test_counts_are_limited(self):
        with self.assertRaises(geo.RoomError):
            geo.validate_openings([door(wall="north"), door(wall="south"), door(wall="west", offset=500)], ROOM)
        with self.assertRaises(geo.RoomError):
            geo.validate_openings([window(wall="north", offset=100 + i * 700, width=500) for i in range(5)], {**ROOM, "width": 6000})

    def test_errors_are_reported_per_opening(self):
        with self.assertRaises(geo.RoomError) as cm:
            geo.validate_openings([door(), door(wall="south", width=100)], ROOM)
        self.assertEqual(set(cm.exception.errors), {"openings.1.width"})


class ItemTests(SimpleTestCase):
    def test_valid_item_inside_the_room(self):
        item, warnings = geo.validate_item(cab(x=100, z=0), ROOM)
        self.assertEqual((item["x"], item["z"], item["rot"]), (100, 0, 0))
        self.assertEqual(warnings, [])
        self.assertEqual(geo.footprint(item), (100, 0, 900, 400))

    def test_item_outside_the_room_is_rejected(self):
        for pos in ({"x": -1}, {"z": -1}, {"x": 3201}, {"z": 2601}):
            with self.assertRaises(geo.RoomError, msg=pos) as cm:
                geo.validate_item(cab(**pos), ROOM)
            self.assertIn("position", cm.exception.errors)
        geo.validate_item(cab(x=3200, z=2600), ROOM)  # touches the walls exactly

    def test_rotated_item_that_sticks_out_of_the_corner_is_rejected(self):
        geo.validate_item(cab(rot=90, x=0, z=0), ROOM)             # footprint 400 x 800
        geo.validate_item(cab(rot=90, x=3600, z=2200), ROOM)       # 4000 x 3000: exactly in the corner
        with self.assertRaises(geo.RoomError):
            geo.validate_item(cab(rot=90, x=3700, z=0), ROOM)      # unrotated it would fit (x1=4500? no): rotated x1=4100
        with self.assertRaises(geo.RoomError):
            geo.validate_item(cab(rot=270, x=0, z=2300), ROOM)     # rotated footprint is 400 x 800, z1 = 3100
        # the same position is fine unrotated
        geo.validate_item(cab(rot=0, x=3200, z=2600), ROOM)

    def test_rotation_must_be_a_multiple_of_ninety(self):
        for bad in (45, 91, -90, 360, "90", True, None):
            with self.assertRaises(geo.RoomError, msg=bad) as cm:
                geo.validate_item(cab(rot=bad), ROOM)
            self.assertIn("rot", cm.exception.errors)
        for ok in (0, 90, 180, 270):
            geo.validate_item(cab(rot=ok, x=500, z=500), ROOM)

    def test_overlap_is_rejected_but_touching_is_allowed(self):
        a, _ = geo.validate_item(cab(x=0, z=0), ROOM)
        with self.assertRaises(geo.RoomError) as cm:
            geo.validate_item(cab(x=700, z=100), ROOM, [a])
        self.assertIn("position", cm.exception.errors)
        geo.validate_item(cab(x=800, z=0), ROOM, [a])   # touches along x
        geo.validate_item(cab(x=0, z=400), ROOM, [a])   # touches along z

    def test_item_can_be_moved_without_colliding_with_itself(self):
        a, _ = geo.validate_item(cab(x=0, z=0), ROOM)
        geo.validate_item({**a, "x": 100}, ROOM, [a])

    def test_engine_rules_apply(self):
        for bad in ({"width": 5000}, {"width": 100}, {"depth": 1200}, {"shelves": -1}, {"doors": 9}, {"shelves": 1.5}, {"width": "800"}):
            with self.assertRaises(geo.RoomError, msg=bad):
                geo.validate_item(cab(**bad), ROOM)

    def test_item_taller_than_the_room(self):
        with self.assertRaises(geo.RoomError) as cm:
            geo.validate_item(cab(height=2400), {**ROOM, "height": 2300})
        self.assertIn("height", cm.exception.errors)

    def test_color_and_text_fields(self):
        with self.assertRaises(geo.RoomError):
            geo.validate_item(cab(color="red"), ROOM)
        with self.assertRaises(geo.RoomError):
            geo.validate_item(cab(name="x" * 81), ROOM)
        self.assertEqual(geo.validate_item(cab(color="#AABBCC"), ROOM)[0]["color"], "#AABBCC")

    def test_blocking_a_door_zone_is_a_warning_not_an_error(self):
        opening = geo.validate_opening(door(), ROOM)                       # north wall, x 1000..1900, zone z 0..800
        item, warnings = geo.validate_item(cab(x=1000, z=0), ROOM, [], [opening])
        self.assertEqual([w["code"] for w in warnings], ["door_zone"])
        self.assertEqual(warnings[0]["item"], item["id"])
        _, ok = geo.validate_item(cab(x=2500, z=0), ROOM, [], [opening])
        self.assertEqual(ok, [])
        _, beside = geo.validate_item(cab(x=100, z=0, width=800), ROOM, [], [opening])   # ends at 900, before the door
        self.assertEqual(beside, [])


class BuildRoomTests(SimpleTestCase):
    def config(self, openings=(), items=()):
        return {"room": ROOM, "openings": [geo.validate_opening(o, ROOM) for o in openings], "items": list(items)}

    @staticmethod
    def hits(b, x0, x1, y0, y1, z0, z1):
        return b["x"] < x1 and x0 < b["x"] + b["sx"] and b["y"] < y1 and y0 < b["y"] + b["sy"] and b["z"] < z1 and z0 < b["z"] + b["sz"]

    def test_empty_room_has_four_walls_floor_ceiling(self):
        built = geo.build_room(self.config())
        kinds = [b["kind"] for b in built["boxes"]]
        self.assertEqual(kinds.count("wall"), 4)
        self.assertEqual((kinds.count("floor"), kinds.count("ceiling")), (1, 1))
        self.assertEqual(built["dimensions"]["width"], 4000)
        self.assertEqual(built["dimensions"]["depth"], 3000)

    def test_all_boxes_are_positive_and_numeric(self):
        item, _ = geo.validate_item(cab(x=100, z=100), ROOM)
        for b in geo.build_room(self.config([door(), window()], [item]))["boxes"]:
            for k in ("sx", "sy", "sz"):
                self.assertGreater(b[k], 0, b)
            for k in ("x", "y", "z"):
                self.assertIsInstance(b[k], (int, float))

    def test_door_leaves_an_opening_in_the_wall(self):
        built = geo.build_room(self.config([door()]))      # north wall, x 1000..1900, 2100 high
        walls = [b for b in built["boxes"] if b["kind"] == "wall" and b["z"] < 0 and b["sz"] == 100]
        self.assertFalse(any(self.hits(b, 1000, 1900, 0, 2100, -100, 0) for b in walls), "the doorway is blocked")
        self.assertTrue(any(self.hits(b, 1000, 1900, 2100, 2700, -100, 0) for b in walls), "no wall above the door")
        self.assertTrue(any(self.hits(b, 0, 1000, 0, 2700, -100, 0) for b in walls))
        self.assertTrue(any(self.hits(b, 1900, 4000, 0, 2700, -100, 0) for b in walls))

    def test_window_has_wall_below_and_above(self):
        built = geo.build_room(self.config([window()]))    # east wall, z 800..2000, sill 900, top 2100
        east = [b for b in built["boxes"] if b["kind"] == "wall" and b["x"] == 4000]
        self.assertTrue(any(self.hits(b, 4000, 4100, 0, 900, 800, 2000) for b in east), "no wall under the window")
        self.assertTrue(any(self.hits(b, 4000, 4100, 2100, 2700, 800, 2000) for b in east), "no wall over the window")
        self.assertFalse(any(self.hits(b, 4000, 4100, 900, 2100, 800, 2000) for b in east), "the window opening is blocked")

    def test_item_boxes_stay_within_the_footprint(self):
        for rot in geo.ROTATIONS:
            item, _ = geo.validate_item(cab(x=1000, z=1000, rot=rot), ROOM)
            x0, z0, x1, z1 = geo.footprint(item)
            mine = [b for b in geo.build_room(self.config([], [item]))["boxes"] if b.get("item") == item["id"]]
            self.assertTrue(mine)
            for b in mine:
                # the back panel sticks out 4 mm behind, door fronts and handles up to 30 mm in front
                self.assertGreaterEqual(b["x"], x0 - 31, (rot, b)); self.assertLessEqual(b["x"] + b["sx"], x1 + 31, (rot, b))
                self.assertGreaterEqual(b["z"], z0 - 31, (rot, b)); self.assertLessEqual(b["z"] + b["sz"], z1 + 31, (rot, b))

    def test_rotation_turns_the_front_towards_the_room(self):
        facing = {}
        for rot in geo.ROTATIONS:
            item, _ = geo.validate_item(cab(x=1000, z=1000, rot=rot, doors=1, shelves=0), ROOM)
            x0, z0, x1, z1 = geo.footprint(item)
            door_box = next(b for b in geo.build_room(self.config([], [item]))["boxes"] if b.get("item") == item["id"] and b["kind"] == "door")
            cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
            facing[rot] = (door_box["x"] + door_box["sx"] / 2 - cx, door_box["z"] + door_box["sz"] / 2 - cz)
        self.assertGreater(facing[0][1], 0)     # +z
        self.assertGreater(facing[90][0], 0)    # +x
        self.assertLess(facing[180][1], 0)      # -z
        self.assertLess(facing[270][0], 0)      # -x

    def test_deterministic(self):
        item, _ = geo.validate_item({**cab(x=300, z=0), "id": "aaaaaaaaaaaa"}, ROOM)
        cfg = self.config([door(), window()], [item])
        self.assertEqual(geo.build_room(cfg), geo.build_room(cfg))

    def test_door_zone_warning_in_the_model(self):
        item, _ = geo.validate_item({**cab(x=1000, z=0), "id": "bbbbbbbbbbbb"}, ROOM)
        built = geo.build_room(self.config([door()], [item]))
        self.assertEqual([w["code"] for w in built["warnings"]], ["door_zone"])


class LayoutTests(SimpleTestCase):
    T = [{"slug": "wardrobe-2door", "name": "Wardrobe", "defaults": {"width": 1000, "height": 2200, "depth": 580, "shelves": 4, "doors": 2, "drawers": 0}},
         {"slug": "bedside", "name": "Bedside", "defaults": {"width": 450, "height": 500, "depth": 400, "shelves": 0, "doors": 0, "drawers": 2}},
         {"slug": "dresser", "name": "Dresser", "defaults": {"width": 900, "height": 1000, "depth": 480, "shelves": 0, "doors": 0, "drawers": 4}}]

    def test_items_are_placed_inside_without_overlap_facing_the_room(self):
        openings = [geo.validate_opening(door(), ROOM)]
        items, warnings = geo.suggest_layout(self.T, ROOM, openings)
        self.assertEqual(len(items), 3, warnings)
        self.assertEqual(warnings, [])
        for i, a in enumerate(items):
            fp = geo.footprint(a)
            self.assertTrue(0 <= fp[0] and fp[2] <= 4000 and 0 <= fp[1] and fp[3] <= 3000)
            for b in items[i + 1:]:
                self.assertFalse(geo._overlap(fp, geo.footprint(b)), (a, b))
        self.assertTrue(all(it["rot"] in geo.WALL_ROT.values() for it in items))

    def test_door_zone_stays_free(self):
        openings = [geo.validate_opening(door(offset=100, width=800), ROOM)]   # zone x 100..900, z 0..800 on the north wall
        items, warnings = geo.suggest_layout(self.T, ROOM, openings)
        self.assertEqual([w for w in warnings if w["code"] == "door_zone"], [])
        zone = geo.door_zones(ROOM, openings)[0]
        self.assertFalse(any(geo._overlap(geo.footprint(i), zone) for i in items))

    def test_longest_wall_is_used_first(self):
        items, _ = geo.suggest_layout(self.T[:1], ROOM, [])
        self.assertEqual(items[0]["rot"], geo.WALL_ROT["north"])               # north/south (4000) beat east/west (3000); north is first
        self.assertEqual((items[0]["x"], items[0]["z"]), (0, 0))

    def test_what_does_not_fit_is_reported_not_placed(self):
        tiny = {"width": 1000, "length": 1000, "height": 2200}
        big = [{"slug": "wide", "name": "Wide unit", "defaults": {"width": 1500, "height": 720, "depth": 560, "shelves": 1, "doors": 2, "drawers": 0}}]
        items, warnings = geo.suggest_layout(big, tiny, [])
        self.assertEqual(items, [])
        self.assertEqual([w["code"] for w in warnings], ["not_placed"])

    def test_room_fills_up_gracefully(self):
        tiny = {"width": 1500, "length": 1500, "height": 2400}
        items, warnings = geo.suggest_layout(self.T * 4, tiny, [])
        self.assertTrue(items)
        self.assertTrue(any(w["code"] == "not_placed" for w in warnings))
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                self.assertFalse(geo._overlap(geo.footprint(a), geo.footprint(b)))

    def test_deterministic_apart_from_ids(self):
        strip = lambda items: [{k: v for k, v in i.items() if k != "id"} for i in items]
        self.assertEqual(strip(geo.suggest_layout(self.T, ROOM, [])[0]), strip(geo.suggest_layout(self.T, ROOM, [])[0]))

    def test_auto_place_single_item(self):
        placed = geo.auto_place({"width": 800, "depth": 400, "height": 2000, "shelves": 3, "doors": 2, "drawers": 0}, ROOM, [], [])
        self.assertIsNotNone(placed)
        none = geo.auto_place({"width": 3900, "depth": 900, "height": 700, "shelves": 0, "doors": 0, "drawers": 0}, {"width": 1000, "length": 1000, "height": 2400}, [], [])
        self.assertIsNone(none)
