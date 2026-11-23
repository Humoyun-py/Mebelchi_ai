# Room design flow (Roadmap v2, Phase 1)

A user builds a room step by step, on the web or in the Telegram bot, and ends with a 3D room they can furnish. Both clients
call the same server-side state machine, so the rules and the questions live in one place. No external AI is used; the model is
deterministic geometry. Room photos are stored as a reference only and are never analysed: sizes are typed by the user.

```
web (JWT)  ─┐
            ├─> apps/rooms/services.py ─> apps/conversations/flow.py   state machine, pure Python
bot (secret) ┘                          └> apps/geometry/room.py       validation + 3D model, pure Python
```

## Steps

`goal -> photo -> elements -> size -> openings -> style -> generate -> furnish -> done`

| Step | Asks | Notes |
|---|---|---|
| goal | kitchen, bedroom, living, wardrobe, office, other | decides which furniture is offered in `elements` |
| photo | an image, or skip | validated like any upload, stored in the gallery (source `room`) |
| elements | doors 0-2, windows 0-4, furniture to place | furniture is a list of template slugs (repeats allowed) |
| size | width, length, height in mm | 1000-15000, 1000-15000, 2000-4500 |
| openings | wall, distance from the wall start, width (and height, sill) for each door and window | skipped when there are none |
| style | modern, classic, minimal, luxury | decides wall and furniture colors |
| generate | nothing | automatic: the room is built and a layout is suggested |
| furnish | add, move, rotate, resize, remove furniture | finish with `{"done": true}` |

Each step has a **descriptor** (`kind`: `choice`, `photo`, `number_group`, `openings`, `furnish`, `summary`) with its fields, limits and
texts in uz/ru/en, plus `value` (the previous answer, to prefill a form). Answering a step discards only the answers that depend on it:
changing the room size or the door count clears the openings; changing the photo or the style costs nothing else.
Answering the style again after going back rebuilds the room and replaces the furniture with a new suggestion (a warning says so).

## Geometry conventions

Millimetres. `x` runs west to east, `z` north to south (north is `z = 0`), `y` is up. The interior is `x in [0, W]`, `z in [0, L]`.
Walls are built outside the interior (100 mm thick). An opening's `offset` is measured from the wall's start: the west end of the north
and south walls, the north end of the west and east walls.

| Rule | Value |
|---|---|
| Door | width 600-1200, height 1800-2400, starts at the floor |
| Window | width 300-3000, height 300-2400, sill 0-1500 |
| Margins | 100 mm from the wall ends and between openings; top of an opening at least 100 mm below the ceiling |
| Furniture | at most 60 items; size and structure are checked by `calculations/engine.py`, so its limits apply |
| Rotation | 0, 90, 180, 270 degrees. 0 faces south (+z), 90 faces east, 180 faces north, 270 faces west |
| Position | `x`, `z` is the minimum corner of the footprint after rotation; the footprint must lie inside the room and may not overlap another item (touching is allowed) |
| Door area | an item inside the 800 mm area in front of a door is a **warning**, not an error |

The footprint is `width x depth`. Door and drawer fronts stick out of it by up to 30 mm; this is not checked.
Every 3D box is axis-aligned, so the existing viewer and the GLB/glTF/OBJ exporters work unchanged.

`Design.config` (schema `room.v1`) holds the room and everything placed in it:

```json
{"schema": "room.v1", "rev": 3, "goal": "kitchen", "style": "modern",
 "room": {"width": 4200, "length": 5000, "height": 2700},
 "openings": [{"id": "...", "type": "door", "wall": "south", "offset": 900, "width": 900, "height": 2100, "sill": 0}],
 "items": [{"id": "...", "template": "wardrobe-2door", "name": "...", "x": 0, "z": 0, "rot": 90, "width": 1000, "depth": 580, "height": 2200,
            "shelves": 4, "doors": 2, "drawers": 0, "color": "#e5e7eb"}]}
```

## API

Web (JWT, own data only; another user's flow is a 404):

| Method | Path | Notes |
|---|---|---|
| POST | `room-flows/` | new flow; returns the view below |
| GET | `room-flows/?status=active`, `room-flows/{id}/` | list and resume; the view has `step`, `descriptor`, `answers`, `rev`, `items`, `openings`, `room`, `warnings` |
| POST | `room-flows/{id}/answer/` | `{step, value}` |
| POST | `room-flows/{id}/back/` | one step back, answers kept |
| POST | `room-flows/{id}/abandon/` | |
| GET | `room-flows/{id}/model/` | `{boxes, dimensions, warnings, rev, ...}`; includes a `ceiling` box (clients hide it for the orbit view) |
| POST | `room-flows/{id}/items/` | `{template?, width, depth, height, x?, z?, rot?, ..., rev}`; without `x`,`z` the item is placed automatically |
| PATCH / DELETE | `room-flows/{id}/items/{item_id}/` | partial update with `rev`; DELETE takes `?rev=` |

Bot (`X-Bot-Secret` header, acting for the account linked to `telegram_id`; an unlinked ID is 404 `not_linked`): the same operations under
`telegram/bot/room-flows/`: `POST /` (resume the active flow, or start one; `{"new": true}` abandons the active one and starts fresh; 200 when
resumed, 201 when created), `GET /{id}/`, `POST /{id}/answer/`, `/back/`, `/abandon/`, `GET /{id}/model/`, `POST /{id}/photo/` (multipart), and
`/{id}/items/`, `/{id}/items/{item_id}/`. `telegram_id` is in the body, or in the query string for GET and DELETE.

Errors use the project envelope `{"error": {"status", "detail", "fields"}}`; `fields.code` carries a machine-readable code:

| Status | `code` | Meaning |
|---|---|---|
| 400 | - | bad value; `fields` names the field (`openings.1.offset`, `position`, `width`, ...) and the stored state is unchanged |
| 409 | `step_mismatch` | the answer was for another step; `expected` says which |
| 409 | `rev_conflict` | the room changed since the client loaded it; `current_rev` is the number to reload |
| 409 | `not_active` | the flow is completed or abandoned and read-only |
| 409 | `not_generated` / `not_furnishing` | the room does not exist yet / the flow is at an earlier step |

Every write to the room carries `rev` (in the body, or an `If-Match` header). It increases by one per write, so two devices cannot overwrite each other.

## Not in Phase 1

Rectangular rooms only. Item rotation is a multiple of 90 degrees. No versioning of designs, no walkthrough and no export (Phase 2).
Photos are not analysed. Backend error messages are in English; the descriptor texts and the bot and web interfaces are in uz, ru and en.
Layouts are visual planning aids, not verified for manufacture and need professional review.

## Tests

```bash
cd backend && python manage.py test apps                       # SQLite; set POSTGRES_* for PostgreSQL 16
cd frontend && npm test && npx tsc -b && npm run build
cd telegram_bot && python -m pytest -q                         # unit tests
# bot against a live backend (scratch database; the backend needs TELEGRAM_BOT_API_SECRET and a roomy THROTTLE_AUTH for repeated runs):
E2E_BASE_URL=http://127.0.0.1:8765/api/v1 E2E_BOT_SECRET=<secret> python -m pytest -q tests/test_room_e2e.py
```
