# MEBELCHI AI REST API

Base URL: `/api/v1/`. Interactive docs: `/api/v1/docs/` (Swagger UI), schema: `/api/v1/schema/`, generated file: [`openapi.yaml`](openapi.yaml). Some endpoints are documented as generic objects in the schema; this page is the precise reference.

## Conventions

- **Auth**: `Authorization: Bearer <access>`. Access tokens last 30 minutes; refresh tokens 14 days and rotate on every refresh (the old one is blacklisted).
- **Units**: millimetres everywhere. Areas in m².
- **Pagination** (list endpoints): `?page=1&page_size=24` (max 100) returns `{count, next, previous, results}`. Lists marked *unpaged* return a plain array.
- **Search/filter/order**: `?search=`, `?ordering=`, plus per-endpoint filters.
- **Errors**: always `{"error": {"status": 400, "detail": "...", "fields": {"width": ["..."]}}}`. 400 validation, 401 unauthenticated, 403 forbidden or plan limit, 404 not found *or not yours*, 429 throttled.
- **Ownership**: every user-owned resource is filtered by the requesting user. Another user's object returns 404.
- **Files**: image/file/avatar `url` fields are signed links valid 15 minutes. They work in `<img>`/`<a>` without a header and are bound to one object.

```bash
curl -X POST /api/v1/auth/login/ -H 'Content-Type: application/json' -d '{"email":"a@x.com","password":"..."}'
curl -X POST /api/v1/calculations/material/ -H "Authorization: Bearer $T" -H 'Content-Type: application/json' \
  -d '{"width":800,"height":2000,"depth":400,"thickness":18,"shelves":3,"doors":2,"drawers":0}'
```

## Public metadata

`GET meta/` (no auth): validation limits, project/furniture categories, board materials, interior rooms and styles, showcase presets, platform stats and all marketing content (features, steps, FAQ) as `{en, uz, ru}` objects. The UI renders these instead of hard-coding them.

## Auth and users

| Method | Path | Notes |
|---|---|---|
| POST | `auth/register/` | `first_name, last_name, email, phone?, password, confirm_password` → `{user, access, refresh}`. Throttled. Can be disabled by the `registration` feature flag |
| POST | `auth/login/` | `{email, password}` → `{access, refresh, user}`. Throttled |
| POST | `auth/refresh/` | `{refresh}` → `{access, refresh}` |
| POST | `auth/google/` | `{credential}` Google ID token (verified with Google, audience must equal `GOOGLE_CLIENT_ID`, email must be verified) → `{user, access, refresh, created}`. Creates the account on first use |
| GET | `auth/config/` | `{google_client_id}` (null when Google sign-in is not configured) |
| POST | `auth/logout/` | `{refresh}` blacklists the token |
| POST | `auth/password-reset/` | `{email}` → always 202 (no enumeration) |
| POST | `auth/password-reset/confirm/` | `{uid, token, new_password}` |
| GET/PATCH | `users/me/` | profile; `role`, `email`, admin flags are read-only here |
| POST | `users/me/role/` | `{role: maker|homeowner}` |
| POST/DELETE | `users/me/avatar/` | multipart `avatar` |
| POST | `users/me/password/` | `{current_password, new_password}` |
| GET/DELETE | `users/me/sessions/`, `users/me/sessions/{id}/` | active refresh tokens; revoke one or all |
| GET | `users/me/storage/` | used/limit bytes, counts |

## Workspace and projects

| Method | Path | Notes |
|---|---|---|
| GET | `workspace/summary/` | counts for sidebar/dashboard |
| CRUD | `folders/` (unpaged) | nested via `parent` |
| CRUD | `projects/` | filters `status, category, pinned, folder`; default list = active only; POST/duplicate/unarchive enforce the plan's project limit |
| POST | `projects/{id}/duplicate/ archive/ unarchive/ pin/` | |
| GET | `projects/{id}/activity/` | |
| GET | `materials/` (unpaged) | system + own; CRUD only on own (`is_system` ones are read-only) |
| GET | `furniture/templates/?category=`, `furniture/categories/` | |

## Engine

| Method | Path | Notes |
|---|---|---|
| POST | `calculations/material/` | body: `width,height,depth,thickness=18,shelves=0,doors=0,drawers=0,back_thickness=4,material,back_material`; optional `save, name, project`; optional cabinet-type and edge parameters (below) and prices (below). Returns `parts[], summary, hardware[], warnings[], assumptions[], requires_professional_review` and, only when prices are requested, `pricing` |
| GET/DELETE | `calculations/`, `calculations/{id}/` | saved results |
| CRUD | `cutting-lists/` | `parts[]` are replaced as a whole on update |
| POST | `cutting-lists/from-calculation/` | cabinet fields + `name, project, sheet_length, sheet_width` |
| POST | `cutting-lists/{id}/optimize/` | `{allow_rotation}` → stored run: groups per material+thickness, sheets with placements, utilization, waste, leftover strip, estimated cost, `unplaced[]` |
| GET | `cutting-lists/{id}/runs/` | last 10 runs |
| GET | `cutting-lists/{id}/export/pdf/` `.../export/xlsx/` | throttled; counts toward the plan's monthly export limit |
| POST | `geometry/preview/` | same body as calculation (+ `color` as `#rrggbb`, `colors`, `handle_style`) → `{dimensions, boxes[], warnings, consistency}`. Public (stateless, anonymous throttle) |
| POST | `geometry/export/{glb|gltf|obj}/` | binary download; throttled |
| CRUD | `designs/` | `kind: furniture|interior`, `config` (≤200 KB), optional `project`, `room_image`. Furniture configs are validated (see below) |
| GET | `designs/{id}/model/` | furniture only: the 3D model (with `consistency`) and the calculation rebuilt from the saved config |
| POST | `designs/{id}/duplicate/` | independent copy named `"<name> (copy)"` |

## Chat

| Method | Path | Notes |
|---|---|---|
| CRUD | `conversations/` | |
| GET/POST | `conversations/{id}/messages/` | POST `{content ≤4000, attachments:[{type:image|file,id}]}` → `[userMessage, assistantMessage]` |
| GET | `conversations/{id}/export/` | Markdown download |
| PATCH | `messages/{id}/` | edit a user message; later messages are replaced and a new reply is generated |
| POST | `messages/{id}/regenerate/ feedback/` | `feedback`: `like|dislike|""` (same value toggles off) |
| DELETE | `messages/{id}/` | |

Assistant message `metadata.intent` is one of `calculation, help, need_input, invalid_input, unsupported`.

## Media

| Method | Path | Notes |
|---|---|---|
| CRUD | `gallery/` | multipart `image` (JPG/PNG/WEBP ≤10 MB, decoded and verified), `source`, `project`; `POST gallery/{id}/favorite/` toggles; filters `favorite, source, project`; `GET gallery/{id}/file/?sig=` (`&download=1`) |
| CRUD | `files/` | multipart `file` (pdf, dwg, dxf, xlsx, csv, txt, glb, gltf, obj, images ≤25 MB; PDFs checked for signature); `GET files/{id}/download/?sig=` |

## Subscriptions, notifications, analytics

| Method | Path | Notes |
|---|---|---|
| GET | `subscriptions/plans/` | public, unpaged |
| GET | `subscriptions/me/` | plan, usage vs limits, payment records |
| POST | `subscriptions/upgrade/` | `{plan}`; free switches instantly, paid creates a *pending* payment (no gateway) |
| GET | `notifications/`, `notifications/unread-count/`; POST `notifications/{id}/read/`, `notifications/read-all/`; DELETE | |
| GET | `analytics/me/`, `analytics/features/` | own usage events; feature flags |

### Cabinet types, edge banding and sliding doors

All of these are optional; omitting them gives exactly the previous behaviour.

| Field | Default | Meaning |
|---|---|---|
| `cabinet_type` | `standard` | `standard`, `kitchen_base`, `kitchen_wall`, `sliding_wardrobe` |
| `edge_thickness` | `0` | mm of edge tape (0-3). When > 0 every part also reports `cut_width`/`cut_height` = finished size minus one tape thickness per banded edge; `cutting-lists/from-calculation/` then stores the cut sizes |
| `plinth_height` | `100` | `kitchen_base`: carcass height = `height - plinth_height`; adds a `Plinth` part, two top rails instead of a top panel, adjustable legs |
| `rail_width` | `100` | `kitchen_base` top rails; `kitchen_wall` hanging rail |
| `sliding_overlap` | `30` | `sliding_wardrobe`: neighbouring panels overlap; panel width = (internal width + (n-1) x overlap) / n |
| `track_top`, `track_bottom` | `35`, `20` | `sliding_wardrobe`: panel height = internal height - both allowances (they depend on the sliding system) |

Rules (400 with a field error): `sliding_wardrobe` needs `doors >= 2` and no drawers; `kitchen_wall` takes no drawers; `kitchen_base` must leave at least 200 mm of body height. The part list, hardware and `assumptions[]` change with the type; `geometry/preview/` builds the 3D model from the same layout.

### 3D model, handles, colours and the consistency proof

`geometry/preview/` and `geometry/export/{glb|gltf|obj}/` take every calculator field plus:

| Field | Meaning |
|---|---|
| `handle_style` | `bar` (default), `knob`, `none`. `none` removes handles from the model **and** from the hardware list; `knob` draws one 24 x 24 x 22 mm knob per door and drawer front. Bar handles are shortened on small fronts so they never overhang |
| `colors` | `{carcass, fronts, back, handle}` hex colours (`#rrggbb`); unlisted groups keep their defaults; wins over the legacy single `color`. Exports carry the colours |

The preview response contains `consistency: {valid, problems[], checks[], not_modelled[]}`. The server checks on every preview that the drawn model **is the calculated cabinet**: overall width/height/depth, number of doors, drawer fronts, shelves and handles (against the hardware list), the size of every drawn component against the calculated part of the same name, and that no two structural components occupy the same space. Drawer boxes inside the cabinet are in the cut list but are not drawn (`not_modelled`). A seeded property test builds thousands of random valid cabinets of all four types and requires `valid: true`.

That check found and fixed real problems, which are now validation rules (400 with a field error): shelves must leave at least 30 mm clear opening; kitchen base top rails may not overlap (`2 x rail_width <= depth`); a hanging rail must fit inside the cabinet; sliding panels in the same lane may not collide (`panel width > 2 x overlap` for 3+ panels). Shelves of a sliding wardrobe are now shallower so they clear both door lanes (`depth - 20 - 2 x thickness - 4 - 5`). A shelf that cuts through a wall cabinet's hanging rail is reported as a warning.

### Saved furniture designs

`config` (schema_version 1): `{"schema_version": 1, "input": {…calculator fields incl. cabinet_type, handle_style…}, "color": "#c9a27a", "colors": {…}, "material": <id|null>}`. On save the server rebuilds the cabinet from `input` and refuses (400, field `config`) anything that could not be built: impossible sizes, a bad `handle_style`, bad hex colours, an unknown colour group, an unsupported `schema_version`. Designs saved by older editors (seven numbers and one `color`) stay valid. `designs/{id}/model/` always recomputes the model from the saved config, so a reopened design reflects the current rules; if stored numbers no longer pass validation it answers 400 with the reason.

### Pricing

Add `prices` (and/or `use_catalog_prices: true`) to `calculations/material/` to get a `pricing` block. **The engine never invents a price**: anything without a price is listed in `missing[]`, `complete` is `false`, and the totals cover only the priced lines.

```json
"prices": {"currency": "UZS", "board_price_per_m2": {"MDF 18": 95000, "HDF": 30000}, "waste_factor": 0.15,
           "edge_price_per_m": 4000, "edge_allowance": 0.05, "hardware_prices": {"Hinge": 12000, "Handle": 25000},
           "labor_per_m2": 60000, "markup_pct": 20}
```

Board price keys are `"<MATERIAL> <thickness>"` (checked first) or `"<MATERIAL>"`. With `use_catalog_prices` the board prices are read from your own materials that have a sheet price (price per sheet / sheet area); explicit prices win; other users' materials are never read. The result lists every `lines[]` entry (`quantity x unit_price = amount`), `subtotals`, `manufacturing_cost`, `markup_amount` and `total_price`; totals are sums of the displayed amounts.

### Optimizer guarantees

Every `optimize/` result is re-checked by an independent routine before it is returned: all parts inside the usable area, no overlaps, saw-kerf clearance between neighbours, each piece placed exactly once with its own size, rotation only where allowed. A failed check raises an error instead of returning a layout. Results carry `validation`, `approximate: true`, `is_optimal: false`, `approximation_note` and `sheet.usable_area` (placement coordinates are relative to the area inside the trim; add `offset_x/offset_y` for sheet coordinates).

## Workshops, orders and tasks

A *workshop* is a tenant: its members, orders and tasks are isolated from every other workshop. Creating one needs the **Workshop** role, which only a platform administrator can assign (`PATCH admin-api/users/{id}/` with `{"role": "workshop"}`; users cannot pick it themselves), and every new workshop starts as **`pending`** until an administrator approves it. Everything below is under `/api/v1/` and uses the usual conventions (Bearer auth, pagination, `{"error": ...}` envelope).

**Who may do what** (checked on the server for every request; an object you may not see answers 404, one you may see but not change answers 403):

| | Owner | Employee (active) | Invited / removed / stranger |
|---|---|---|---|
| Workshop info, status, logo | read + change | read | nothing (404) |
| Members | list all (with emails), invite, remove, transfer ownership | list active colleagues (names only) | only own invitation row |
| Orders | all of the workshop: create, edit, change status, delete (rules below) | read-only: orders assigned to them or containing a task assigned to them, **without money fields** | nothing |
| Tasks | all: create, assign, edit, change any valid status, delete (rules below) | read their assigned tasks; change only the status (`pending -> in_progress -> review`, `review -> in_progress`) | nothing |
| Statistics | yes | no (403) | nothing |

Workshop status: `pending` (waiting for approval) -> `active`; or `rejected` (an administrator declined it and gave a reason in `review_note`, which the owner can read). Only `active` workshops accept orders, tasks and invitations; `pending`, `rejected`, `inactive` and `suspended` ones are read-only, and a suspended one is frozen even for its owner. The owner can switch only between `active` and `inactive`; every other change is an administrator decision (see "Administration"). Platform staff have no special access to workshop data through these endpoints.

### Workshops

| Method | Path | Notes |
|---|---|---|
| GET | `workshops/` | workshops where you are an active member; each has `my_role`. Filters `status`; `?search=`; `?ordering=name\|created_at\|status` |
| POST | `workshops/` | Workshop role only (403 otherwise). `{name, description?, phone?, email?, address?}`; you become the owner; the workshop is created `pending`. `slug` is generated and never changes |
| GET / PATCH | `workshops/{id}/` | PATCH owner only; `status` may be `active` or `inactive` (approval, rejection and suspension are administrator-only; `review_note` is read-only) |
| DELETE | `workshops/{id}/` | owner only; **409** if the workshop has orders or tasks (set it `inactive` instead) |
| GET | `workshops/{id}/statistics/` | owner only, see below |
| POST / DELETE | `workshops/{id}/logo/` | multipart `logo` (JPG/PNG/WEBP, 10 MB, validated by decoding); `logo_url` is a 15-minute signed link |

### Members and invitations

| Method | Path | Notes |
|---|---|---|
| GET | `workshops/{id}/members/` | owner: every row incl. `invited`/`removed` (filter `status`, `role`); employees: active roster, no emails |
| POST | `workshops/{id}/members/` | owner: `{email}` of an existing account -> `invited` employee; the person gets a notification. 400 if already a member/invited or unknown |
| PATCH | `workshops/{id}/members/{mid}/` | **the invited person**: `{status: "active"}` accepts, `{status: "removed"}` declines; an employee leaves with `{status: "removed"}`. **owner**: `{role: "owner", confirm_transfer: true}` hands ownership to an active employee (you become an employee) |
| DELETE | `workshops/{id}/members/{mid}/` | owner removes an employee. **Soft**: the row stays with `status: removed`, so orders, tasks and history keep pointing at it. The owner cannot be removed |
| GET | `workshop-invitations/` | my pending invitations |

A workshop always has exactly one owner (database constraints: one owner row per workshop, the owner row is always active, one membership per user and workshop). A user can be a member of many workshops with a different role in each.

### Orders

| Method | Path | Notes |
|---|---|---|
| GET | `orders/` | owner: all orders of their workshops; employee: assigned / task-linked orders. Filters `workshop, status, payment_status, assigned_employee, deadline_after, deadline_before, created_after, created_before, overdue, mine`; `?search=` over number, title, customer name and phone; `?ordering=created_at\|updated_at\|deadline\|status\|order_number\|total_price` (NULL deadlines sort last). `payment_status` filters and `total_price` sorting are limited for people who are employees somewhere: they must also pass `workshop=<a workshop you own>` |
| POST | `orders/` | owner only: `workshop` (required), `title`, `customer_name` (required), `customer_phone/email/address`, `description`, `related_project` (your own project), `total_price`, `paid_amount`, `assigned_employee` (member id), `start_date`, `deadline` |
| GET | `orders/{id}/` | adds `status_history[]` and `tasks_count`. Every order also carries `allowed_next_statuses[]`: the statuses the caller may move it to right now (empty for employees, final orders and read-only workshops) |
| PATCH | `orders/{id}/` | owner only: any field above plus `status` (+ `status_note`). `workshop` cannot change |
| DELETE | `orders/{id}/` | owner only, only `new`/`cancelled` orders **with nothing paid**; otherwise **409** (cancel instead) |

`order_number` is `ORD-<workshop id>-<sequence>` (atomic per-workshop counter, unique, never reused). Money is a decimal string with 2 places; employees do not receive `total_price`, `paid_amount`, `payment_status`, `outstanding_amount` or `customer_user`.

**Status lifecycle** (anything else is a 400 that lists the allowed next statuses):

```
new -> confirmed -> in_production -> ready -> delivered
 \______\______________\___________/  (new, confirmed, in_production, ready) -> cancelled
ready -> in_production   (rework)
```

Entering `in_production` sets `start_date` (if empty); `delivered` sets `completed_at`; `cancelled` cancels the order's open tasks in the same transaction. `delivered` and `cancelled` are final: only payment fields can still be edited. Tasks cannot be added to final orders.

**Payments** (records only, no payment gateway): `payment_status` is derived from `paid_amount` (`unpaid`, `partially_paid`, `paid`); `paid_amount` may not exceed `total_price` (also a database CHECK). `payment_status: "refunded"` may be set explicitly once something was paid; the paid amount is kept as the historical record, the payment record is then closed, and the order counts as zero outstanding.

### Tasks

| Method | Path | Notes |
|---|---|---|
| GET | `tasks/` | owner: all of their workshops; employee: assigned to them. Filters `workshop, order, assigned_to` (alias `employee`), `status, priority, deadline_after, deadline_before, overdue, mine`; search over title, description, order number; ordering `created_at\|updated_at\|deadline\|priority\|status` |
| POST | `tasks/` | owner only: `title`, `order` (workshop is taken from it) or `workshop`, `assigned_to` (active member id), `priority` (`low/medium/high/urgent`), `deadline` (future), `description` |
| GET | `tasks/{id}/` | adds `status_history[]`. Every task carries `allowed_next_statuses[]` for the caller (owner: all valid moves; assignee: only the employee moves; nothing for read-only workshops) |
| PATCH | `tasks/{id}/` | owner: any field + status; assignee: `status` only (anything else 403). `order` and `workshop` cannot change |
| DELETE | `tasks/{id}/` | owner only, only tasks never started (`pending`/`cancelled`); otherwise **409** |

Task lifecycle: `pending -> in_progress -> review -> completed`; owners may also complete straight from `in_progress`, send `in_progress <-> pending`/`review -> in_progress`, or cancel from any open status. `completed` and `cancelled` are final. `started_at` is set the first time work starts, `completed_at` on completion. An order's task must belong to the same workshop, and `assigned_to` must be an *active* member of it.

### Statistics

`GET workshops/{id}/statistics/` (owner) returns `orders` (total, per status, `completed` = delivered), `employees` (total/active/invited, owner excluded), `tasks` (total, per status, `overdue` = open and past deadline) and `money`. `money.total_order_value` sums non-cancelled orders; `paid_amount` sums paid amounts of non-refunded orders; `outstanding_amount` is total minus paid over orders that are neither cancelled nor refunded. Everything is aggregated in the database (3 aggregate queries, constant in the number of rows).

```bash
# create a workshop, invite someone, create an order and a task
curl -X POST /api/v1/workshops/ -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"name":"Samarkand Furniture"}'
curl -X POST /api/v1/workshops/1/members/ -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"email":"master@example.com"}'
curl -X POST /api/v1/orders/ -H "Authorization: Bearer $T" -H 'Content-Type: application/json' \
  -d '{"workshop":1,"title":"Kitchen 3.2 m","customer_name":"Ali Valiyev","total_price":"12000000","paid_amount":"3000000","deadline":"2026-12-20"}'
curl -X PATCH /api/v1/orders/1/ -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"status":"confirmed","status_note":"Deposit received"}'
curl -X POST /api/v1/tasks/ -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"order":1,"title":"Cut carcass panels","assigned_to":2,"priority":"high","deadline":"2026-12-05T17:00:00Z"}'
curl -X PATCH /api/v1/tasks/1/ -H "Authorization: Bearer $EMPLOYEE_T" -H 'Content-Type: application/json' -d '{"status":"in_progress"}'   # the assignee reports progress
```

## Room design (`rooms/`)

A guided conversation that ends in a 3D room with furniture, saved as an `interior` design (`config.schema = "room.v1"`, units are millimetres). The web app and the Telegram bot are meant to drive the same flow. It is deterministic: no external AI, and photos are stored only as a reference (never analysed). Layouts are planning aids, not verified for manufacture.

Steps: `goal` -> `photo` (optional) -> `elements` -> `size` -> `openings` (skipped when there are no doors or windows) -> `style` -> `furnish` -> `done`. Every response carries the current `question` (kind, fields, options and limits in en/uz/ru), so a client renders it from the response alone. Every route is scoped to the signed-in user; a flow that is not yours answers 404.

| Method | Path | Notes |
|---|---|---|
| GET | `rooms/` | your flows, newest activity first; `?status=active\|completed\|abandoned` |
| POST | `rooms/` | starts a flow at `goal`; **409** after 20 unfinished flows |
| GET / DELETE | `rooms/{id}/` | state, `question`, `design` id and `room` (`config` + `warnings`). DELETE removes the flow and **keeps** the saved design |
| POST | `rooms/{id}/answer/` | `{"step": "<current step>", "value": ...}`. **409** (`expected_step`) when `step` is not the current step; **400** with `error.fields` for a bad value. Values: `goal` an id; `photo` `{"skip": true}` or `{"image_id": n}` (must be your own gallery image); `elements` `{doors, windows, furniture:[template slugs]}`; `size` `{width, length, height}`; `openings` `[{type, wall, offset, width, height, sill}]`; `style` an id; `furnish` `{"done": true}` |
| POST | `rooms/{id}/back/` | one step back, keeping every answer |
| POST | `rooms/{id}/finish/` | only in `furnish`; the flow becomes `completed` and read-only |
| GET | `rooms/{id}/model/` | boxes for the 3D viewer (walls with openings, floor, ceiling, furniture), rebuilt from the saved config |
| POST | `rooms/{id}/items/` | `{"template": slug, x?, z?, rot?, width?, depth?, height?, shelves?, doors?, drawers?, color?, name?}`; without `x` and `z` the item is placed automatically (400 `position` when it fits nowhere); at most 60 items |
| PATCH / DELETE | `rooms/{id}/items/{item_id}/` | PATCH moves, rotates (`rot` 0/90/180/270) or resizes; `id` and `template` cannot change |
| POST | `rooms/{id}/reset-layout/` | discards manual placements and lays the chosen furniture out again |
| POST | `rooms/import-design/` | body `{"design": <id>}`. Opens an **old interior design** (no `room_flow`) in the room designer: 201 the first time, 200 when it was imported before (same flow, edits kept). The old design is never changed; the room designer works on a copy with the same name, project and photo, config `room.v1`, and the old config under `config.legacy`. 404 not yours / not an interior design, 400 names the old field that cannot be converted (`roomW`, `roomL`, `roomH`), 409 when 20 unfinished room designs exist or the design is already `room.v1` without a conversation |

Answering `style` builds the room; answering it again later (after `back`) **rebuilds it and replaces manual placements**. Items must stay inside the room and must not overlap (400 otherwise); standing in front of a door (800 mm zone) is a **warning** (`door_zone`), not an error. Item and answer changes return the whole flow plus `item` and `item_warnings`. A design built by a flow has `room_flow` (its id) in `designs/` responses; the web app uses it to reopen the room in the room designer. The size and structure of every cabinet are checked by the same engine as the furniture editor.

### Room project files, settings and GLB (Phase 2A)
| Method | Path | Notes |
|---|---|---|
| GET | `rooms/{id}/export/` | the design as a `.mebelchi` file (`application/vnd.mebelchi+json`) |
| POST | `rooms/import/` | multipart `file` (or the document as JSON) creates a NEW design; 400 names the place in the file (`furniture.2.position`, `checksum` ...); `unknown_models` lists catalogue ids this server lacks |
| GET | `rooms/{id}/export-glb/` | the 3D room as a standard GLB (coloured boxes, no textures) |
| PATCH | `rooms/{id}/settings/` | `wall`, `floor` (hex), `floor_material` (wood/laminate/tile/concrete/carpet), `light` `{intensity 0.2-2, warm}`, `camera` `{position, target, fov}`; furnish step only |

`.mebelchi` is a versioned JSON project (room, openings, furniture with positions, colours, camera, light, catalogue ids of the models used) with a SHA-256 of its content. The checksum detects accidental damage or hand edits; it is **not** a signature and **not** copy protection: anyone holding the file can read it. Imports are validated like typed input, so a hand-written file cannot create an impossible room.

## Furniture catalogue (`furniture/templates/`)
`GET` list (plain array) / `GET {id}` for every signed-in user: approved items, plus your own workshop's items in any state; staff see all. Filters `category`, `workshop`, `status`, `is_available`, `search`, `ordering` (name, price, category, created_at).
| Method | Path | Notes |
|---|---|---|
| POST | `furniture/templates/` | workshop owner (of an active workshop) or staff. Body: `workshop`, `category`, `name`, `description`, `price`, `currency`, `material`, `color`, `manufacturer`, `lead_time_days`, `is_available` and either `defaults` or `width`/`height`/`depth` (+ `thickness`, `shelves`, `doors`, `drawers`). Sizes are validated by the cabinet engine. Workshop items start `pending`; staff items are `approved` |
| PATCH/PUT/DELETE | `furniture/templates/{id}/` | owner of the item's workshop or staff; DELETE hides the item (history kept). Changing name, category, sizes or the model sends an approved item back to review; price, stock and wording do not |
| POST | `furniture/templates/{id}/review/` | staff only: `{status: approved\|rejected, note}` (a rejection needs a reason) |
| POST/DELETE | `furniture/templates/{id}/images/` | multipart `view` (front/left/right/back/top/bottom) + `image`; one image per side, uploading again replaces it; `DELETE ?view=` |
| POST/DELETE | `furniture/templates/{id}/model/` | multipart `file` = a `.glb` (glTF 2.0, <= 15 MB, no external references). DELETE returns to the generated model |
| GET | `furniture/templates/{id}/export/glb\|gltf/` | the uploaded GLB, or a model generated from the sizes (plain boxes, not photo-real) |
A workshop cannot have two active items with the same category, name and size (400). Pending and rejected items are never offered by the room designer. Image URLs are short-lived signed links.

## Marketplace (`marketplace/`)
Asking for matches creates nothing and contacts nobody; placing an order is the only step that reaches a workshop.
| Method | Path | Notes |
|---|---|---|
| POST | `marketplace/match/` | body: `catalog_item` (id) or `furniture` `{category, width, height, depth, ...}`; optional `quantity`, `customer_location` `{latitude, longitude}`, `budget`, `deadline_days`, `currency`, `limit` (1-10, default 3), `exclude_workshops`. Returns ranked `options` (price, `price_tier` min/average/premium, distance (straight line), rating, lead time, load, `score` + `score_parts`, `flags`, price `quote`, `portfolio`), `tiers` over all quotes received, and `excluded` with the reason for every workshop left out |
| POST | `marketplace/orders/` | match body + `workshop` (+ `customer_name`, `customer_phone`, `customer_address`, `notes`). The price is recomputed on the server (a sent price is ignored). Creates a `pending` order; the workshop has 24 h and is reminded every 4 h (max 6) |
| GET | `marketplace/orders/`, `{id}/` | the customer's own orders (never employees, tasks or the commission split) |
| POST | `marketplace/orders/{id}/cancel/` | before production and with nothing paid |
| GET/POST | `marketplace/orders/{id}/alternatives/`, `reassign/` | rejected orders: other workshops (the refusing ones are never offered) / send it to one as a new pending order |
| POST | `marketplace/orders/{id}/payments/` | `{amount, method, reference, idempotency_key}`: reports a payment; it counts only after an administrator confirms it |
| POST | `marketplace/orders/{id}/review/` | `{stars 1-5, comment}` once, after completion; updates the workshop rating |
Ranking (deterministic, no AI): hard filters (active, accepting orders, makes the category, complete price list, same currency, delivers there, meets the deadline, free capacity), then a score from price 35, distance 20, rating 20, lead time 15, load 10 (over-budget offers are demoted but shown). Prices come only from the workshop's own `price_list`, catalogue prices, transport rate (per km, from the straight-line distance) and assembly percentage; a workshop whose price list does not cover the furniture gets no quote and is listed under `excluded`.

**Order statuses** (workshop `orders/`): `new` (made by the workshop), `pending` (marketplace, waiting), `confirmed` (= *Accepted*), `rejected` (reason required, final), `in_production`, `quality_check`, `ready`, `delivery`, `delivered` (= *Completed*), `cancelled`. `allowed_next_statuses` on each order lists the legal moves. Marketplace orders' price and payment fields cannot be edited by the workshop.

**Workshop profile** (`workshops/{id}/`, owner): `latitude`+`longitude` (both or neither), `delivery_radius_km`, `categories`, `working_hours`, `max_active_orders`, `is_accepting_orders`, `lead_time_days`, `price_list` (engine PriceList: board per m2, edge tape, hardware, labour, markup), `transport_per_km`, `assembly_percent`; read-only `rating_avg`, `rating_count`.

## Finance (`admin-api/finance/`, staff only)
No payment provider is connected and no money moves through the platform: payments are records that an administrator confirms by hand.
| Method | Path | Notes |
|---|---|---|
| GET/PATCH | `commission/` | `{commission_percent}` default **20.00**; new orders use the new rate, placed orders keep theirs (snapshot on the order) |
| GET/POST | `payments/` | list (filters `status`, `kind`, `order`); POST `{order, kind: payment\|refund, amount, method, reference, confirm}` records (and with `confirm: true` confirms) |
| POST | `payments/{id}/confirm/`, `reject/` | confirm adds to the order's `paid_amount`; reject needs `{reason}`. A payment can be decided once |
| GET | `summary/` | `?from=&to=&workshop=`: booked orders (total / commission / workshop amount), collected payments and refunds, per-workshop share covered by money received |
Commission = `round_half_up(total x percent / 100)`, workshop amount = total - commission (always adds up to the cent; $1000 -> $200 / $800). A full refund closes the order's payment record. Unique `idempotency_key` per order and unique receipt `reference` prevent double counting.

## AI status (`ai/status/`)
`GET` -> `{enabled, provider, capabilities, available_providers, message}`. With no provider configured `enabled` is false and nothing pretends otherwise. See `apps/ai/providers.py` to add one; prices, geometry and matching never call a provider.

## Administration (`admin-api/`, staff only, otherwise 403)

### Workshop review (`admin-api/workshops/`, platform admins only)

| Method | Path | Notes |
|---|---|---|
| GET | `admin-api/workshops/` | filters `status` (`pending`, `active`, `rejected`, `suspended`, `inactive`), `kind`, `city`; `?search=` (name, slug, city, owner email); each row has `owner_email`, `member_count`, `order_count`, `review_note` |
| POST | `admin-api/workshops/{id}/approve/` | `{note?}`; `pending`, `rejected`, `suspended` or `inactive` -> `active` |
| POST | `admin-api/workshops/{id}/reject/` | `{note}` is **required** (400 without it); only `pending` -> `rejected`; the owner is notified and sees the reason in `review_note` |
| POST | `admin-api/workshops/{id}/suspend/` | `{note?}`; `active` -> `suspended` |
| GET | `admin-api/audit-logs/?model=workshops.workshop&object_id={id}` | the history of one workshop (events `workshop.created`, `.approved`, `.rejected`, `.suspended`, `.reactivated`, ...) |
| PATCH | `admin-api/users/{id}/` | `{role}` assigns `homeowner`, `maker` or `workshop`; audited as `user.role_changed` |

A decision that is not allowed from the current status answers 400 and changes nothing (no audit row, no notification). Two administrators deciding at once: the second one gets 400. Administrators have no access to a workshop's orders or tasks.

`stats/`, `users/` (PATCH `is_active`, `is_staff`, `role`; cannot lock yourself out; only superusers change `is_staff`), `projects/`, `subscriptions/` (PATCH `plan_slug`), `payments/` (+ `POST {id}/confirm/` activates the plan, `{id}/reject/`), `logs/` (5xx errors), `features/` (CRUD flags), `broadcast/` (POST notification to all users), `storage/`.

### Audit log (`admin-api/audit-logs/`, platform admins only, read-only)

Append-only record of who did what: `actor`, `actor_email` (kept if the account is deleted), `action` (`create|update|delete|login|logout|password`), `event` (business event such as `order.status_changed`, empty for plain changes; filterable), `model` (`app.model`), `object_id`, `object_repr`, `changes` (`{field: {old, new}}` for updates), `ip`, `method`, `path`, `created_at`. Filters: `action`, `model`, `object_id`, `actor`, `actor_email`, `created_after`, `created_before`; `?search=` over email, object and path; paginated, newest first. Passwords and fields containing `password`/`token`/`secret`/`api_key` are stored as `[redacted]`; values over 200 characters are truncated. Create/update/delete are recorded automatically for users, folders, projects, materials, calculations, cutting lists, designs, gallery images, files, conversations, plans, subscriptions, payments, feature flags, **workshops, members, orders and tasks**. Workshop events: `workshop.created/updated/owner_changed/deleted`, `member.invited/accepted/declined/left/removed/role_changed`, `order.created/updated/status_changed/deleted`, `task.created/updated/assigned/status_changed/completed/deleted`. Customer phone, email and address are logged as `[redacted]` (the log shows *that* they changed, not their values). `QuerySet.update()`, `bulk_create()` and raw SQL do not send Django signals and are therefore not recorded automatically (cutting-list part replacement is recorded explicitly). Set `AUDIT_IP_HEADER=HTTP_X_REAL_IP` only behind a proxy that overwrites that header (docker-compose does); otherwise the IP is `REMOTE_ADDR`.

### Android app releases (`app/android/`, public, no login)

| Method | Path | Notes |
|---|---|---|
| GET | `app/android/` | `{latest, releases[]}`, newest first, only **published production** builds. Each entry: `version_name`, `version_code`, `sha256`, `size_bytes`, `notes`, `published_at`, `download_url`. `latest` is `null` until a build is published. |
| GET | `app/android/latest/download/` | the newest published APK |
| GET | `app/android/{version_code}/download/` | a specific published APK; 404 for unpublished, development or unknown builds |

The APK answers with `Content-Type: application/vnd.android.package-archive`, `X-Content-SHA256` and `X-Content-Type-Options: nosniff`. Behind nginx (`RELEASES_X_ACCEL_PREFIX` set in docker-compose) the file is streamed by nginx through `X-Accel-Redirect`; Django still decides whether it may be served and counts the download. `/media/` stays closed. The website page is `/android`.

Data model `releases.AppRelease`: platform, channel (`production` | `development`; development builds are never public), version name and code (unique per platform + channel; a lower code cannot be published after a higher one because Android refuses downgrades), the file, `sha256` and size computed from the file at registration, notes, `is_published`, download counter. Add builds with `manage.py publish_android_release` (see DEPLOYMENT.md section 11); administrators publish/unpublish and edit notes in the Django admin; changes are audited.
