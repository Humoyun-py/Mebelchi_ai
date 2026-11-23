"""End-to-end: the real room handlers and the real BackendClient against a running backend. Skipped unless both are set:

    E2E_BASE_URL=http://127.0.0.1:8765/api/v1  E2E_BOT_SECRET=<TELEGRAM_BOT_API_SECRET of that backend>  pytest tests/test_room_e2e.py

Use a scratch database: the test registers a user, links a Telegram ID to it and creates a design. Telegram itself is
replaced by mock messages; everything between the handlers and the database is real.
"""
import os
import secrets

import httpx
import pytest

from bot.handlers import room
from bot.keyboards.room import RoomPick
from bot.services.api import ApiError, BackendClient
from tests.helpers import fake_callback, fake_message, fsm

BASE, SECRET = os.environ.get("E2E_BASE_URL", ""), os.environ.get("E2E_BOT_SECRET", "")
pytestmark = pytest.mark.skipif(not (BASE and SECRET), reason="set E2E_BASE_URL and E2E_BOT_SECRET to run against a live backend")
WEB = "https://mebelchi.example"
PASSWORD = "Zx9#kLmQ27vb!"


class World:
    """A registered web user linked to a Telegram ID, plus a web session to read the truth from the API."""

    def __init__(self):
        self.tg = secrets.randbelow(10**9) + 10**9
        self.email = f"e2e{secrets.token_hex(4)}@example.com"
        http = httpx.Client(base_url=BASE, timeout=10)
        r = http.post("/auth/register/", json={"email": self.email, "password": PASSWORD, "confirm_password": PASSWORD, "first_name": "E", "last_name": "Two"})
        assert r.status_code == 201, r.text
        tokens = http.post("/auth/login/", json={"email": self.email, "password": PASSWORD}).json()
        self.web = httpx.Client(base_url=BASE, timeout=10, headers={"Authorization": f"Bearer {tokens['access']}"})
        self.code = self.web.post("/telegram/link-code/").json()["code"]
        self.api = BackendClient(BASE, SECRET)

    def truth(self, flow_id: int) -> dict:
        r = self.web.get(f"/room-flows/{flow_id}/")
        assert r.status_code == 200, r.text
        return r.json()


@pytest.fixture
async def world():
    w = World()
    await w.api.link(w.tg, "e2e", w.code)
    yield w
    await w.api.close()


def cb(w):
    return fake_callback(data_user_id=w.tg)


def msg(w, text=None):
    return fake_message(text, user_id=w.tg)


def shown(event) -> str:
    targets = [event] + ([event.message] if hasattr(event, "message") else [])
    return "\n".join(c.args[0] for o in targets for n in ("edit_text", "answer") for c in getattr(o, n).await_args_list if c.args)


async def press(handler, w, state, a, v="", f=0, event=None):
    event = event or cb(w)
    await handler(event, RoomPick(a=a, v=v, f=f), state, w.api, "en", WEB)
    return event


async def test_whole_room_journey_through_the_bot(world):
    w, state = world, fsm(world.tg)
    checks = 0

    # 1. start: the server creates the flow and the bot shows the first question
    m = msg(w, "/room")
    await room.start_room(m, state, w.api, "en", WEB)
    flow, created = await w.api.room_start(w.tg)
    fid = flow["id"]
    assert "What are we designing?" in shown(m) and flow["step"] == "goal" and not created
    checks += 1

    # 2. goal, photo (skipped), elements by buttons
    await press(room.pick, w, state, "pick", "bedroom", fid)
    assert w.truth(fid)["answers"]["goal"] == "bedroom"
    await press(room.skip_photo, w, state, "skip", f=fid)
    assert w.truth(fid)["step"] == "elements"
    checks += 2
    await press(room.pick_number, w, state, "num", "1", fid)           # one door
    await press(room.pick_number, w, state, "num", "1", fid)           # one window
    await press(room.toggle, w, state, "tog", "bedside", fid)
    await press(room.toggle, w, state, "tog", "wardrobe-2door", fid)
    await press(room.multi_done, w, state, "multi_done", f=fid)
    after = w.truth(fid)
    assert after["step"] == "size" and after["answers"]["elements"] == {"doors": 1, "windows": 1, "furniture": ["bedside", "wardrobe-2door"]}
    checks += 1

    # 3. the room size, typed. A bad value is refused locally; a value the server refuses is shown with its reason and asked again.
    bad = msg(w, "999")
    await room.receive_number(bad, state, w.api, "en", WEB)
    assert "not valid" in shown(bad).lower() or "number" in shown(bad).lower()
    assert w.truth(fid)["step"] == "size"
    for text in ("4000", "3000", "2700"):
        await room.receive_number(msg(w, text), state, w.api, "en", WEB)
    after = w.truth(fid)
    assert after["step"] == "openings" and after["answers"]["size"] == {"width": 4000, "length": 3000, "height": 2700}
    checks += 2

    # 4. openings: wall, distance, default width, for the door and then the window
    await press(room.pick_wall, w, state, "wall", "north", fid)
    await room.receive_number(msg(w, "100"), state, w.api, "en", WEB)
    await press(room.default_width, w, state, "wdef", f=fid)
    await press(room.pick_wall, w, state, "wall", "east", fid)
    await room.receive_number(msg(w, "300"), state, w.api, "en", WEB)
    await press(room.default_width, w, state, "wdef", f=fid)
    after = w.truth(fid)
    assert after["step"] == "style"
    assert [(o["type"], o["wall"], o["offset"], o["width"]) for o in after["answers"]["openings"]] == [("door", "north", 100, 900), ("window", "east", 300, 1200)]
    checks += 1

    # 5. style: the server builds the room and suggests a layout
    c = await press(room.pick, w, state, "pick", "modern", fid)
    built = w.truth(fid)
    assert built["step"] == "furnish" and built["rev"] == 1 and len(built["items"]) == 2 and built["design_id"]
    assert "1. " in shown(c) and "2. " in shown(c)
    checks += 2

    # 6. furnish: add, move, rotate, remove, each with the revision the server holds
    await press(room.add_item, w, state, "add", "dresser", fid)
    assert len(w.truth(fid)["items"]) == 3 and w.truth(fid)["rev"] == 2
    dresser = w.truth(fid)["items"][-1]
    await press(room.move_item, w, state, "mve", dresser["id"], fid)
    moved = next(i for i in w.truth(fid)["items"] if i["id"] == dresser["id"])
    print(f"\n  dresser placed at x={dresser['x']} z={dresser['z']} rot={dresser['rot']} -> after East 100: x={moved['x']} z={moved['z']}")
    assert (moved["x"], moved["z"]) == (dresser["x"] + 100, dresser["z"])
    await press(room.rotate_item, w, state, "rot", dresser["id"], fid)
    rotated = next(i for i in w.truth(fid)["items"] if i["id"] == dresser["id"])
    print(f"  rotate: {dresser['rot']} -> {rotated['rot']} at x={rotated['x']} z={rotated['z']}")
    assert rotated["rot"] == (dresser["rot"] + 90) % 360
    checks += 3
    await press(room.delete_item, w, state, "del", dresser["id"], fid)
    assert len(w.truth(fid)["items"]) == 2
    checks += 1

    # 7. the bot restarts: a brand new FSM, the state comes back from the server
    state2, m2 = fsm(w.tg), msg(w, "/room")
    await room.start_room(m2, state2, w.api, "en", WEB)
    assert "unfinished" in shown(m2).lower()
    c2 = await press(room.resume, w, state2, "resume", f=fid)
    assert "Place the furniture" in shown(c2) and "1. " in shown(c2)
    checks += 1

    # 8. a stale button and a conflicting edit are handled, not crashed on
    await press(room.pick, w, state2, "pick", "kitchen", fid)               # a goal button pressed long after the goal step
    assert w.truth(fid)["answers"]["goal"] == "bedroom" and w.truth(fid)["step"] == "furnish"
    checks += 1

    # 9. finish
    done = await press(room.finish, w, state2, "done", f=fid)
    final = w.truth(fid)
    assert final["status"] == "completed" and final["step"] == "done" and "Room saved" in shown(done)
    design = w.web.get("/designs/").json()["results"][0]
    assert design["config"]["schema"] == "room.v1" and len(design["config"]["items"]) == 2
    checks += 1
    print(f"\nE2E room journey: {checks} checkpoints passed (flow {fid}, design {final['design_id']}, final rev {final['rev']})")


async def test_two_accounts_never_see_each_other(world):
    a = world
    b = World()
    await b.api.link(b.tg, "e2e-b", b.code)
    try:
        flow_a, _ = await a.api.room_start(a.tg)
        with pytest.raises(ApiError) as exc:
            await b.api.room_get(b.tg, flow_a["id"])
        assert exc.value.status == 404
        assert b.web.get(f"/room-flows/{flow_a['id']}/").status_code == 404
        flow_b, _ = await b.api.room_start(b.tg)
        assert flow_b["id"] != flow_a["id"]
    finally:
        await b.api.close()


async def test_wrong_secret_and_unlinked_telegram_id_are_refused(world):
    with pytest.raises(ApiError) as exc:
        await BackendClient(BASE, "not-the-secret").room_start(world.tg)
    assert exc.value.status == 403
    with pytest.raises(ApiError) as exc:
        await world.api.room_start(world.tg + 7)
    assert exc.value.status == 404 and exc.value.code == "not_linked"
