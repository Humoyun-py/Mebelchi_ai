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
| POST | `geometry/preview/` | same body as calculation (+ `color` as `#rrggbb`) → `{dimensions, boxes[], warnings}`. Public (stateless, anonymous throttle) |
| POST | `geometry/export/{glb|gltf|obj}/` | binary download; throttled |
| CRUD | `designs/` | `kind: furniture|interior`, free-form `config` (≤200 KB), optional `project`, `room_image` |

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

A *workshop* is a tenant: its members, orders and tasks are isolated from every other workshop. Creating one needs the Furniture Maker role. Everything below is under `/api/v1/` and uses the usual conventions (Bearer auth, pagination, `{"error": ...}` envelope).

**Who may do what** (checked on the server for every request; an object you may not see answers 404, one you may see but not change answers 403):

| | Owner | Employee (active) | Invited / removed / stranger |
|---|---|---|---|
| Workshop info, status, logo | read + change | read | nothing (404) |
| Members | list all (with emails), invite, remove, transfer ownership | list active colleagues (names only) | only own invitation row |
| Orders | all of the workshop: create, edit, change status, delete (rules below) | read-only: orders assigned to them or containing a task assigned to them, **without money fields** | nothing |
| Tasks | all: create, assign, edit, change any valid status, delete (rules below) | read their assigned tasks; change only the status (`pending -> in_progress -> review`, `review -> in_progress`) | nothing |
| Statistics | yes | no (403) | nothing |

An inactive workshop is read-only; a suspended one (set by platform staff in the Django admin) is frozen even for its owner. Platform staff have no special access to workshop data through these endpoints.

### Workshops

| Method | Path | Notes |
|---|---|---|
| GET | `workshops/` | workshops where you are an active member; each has `my_role`. Filters `status`; `?search=`; `?ordering=name\|created_at\|status` |
| POST | `workshops/` | `{name, description?, phone?, email?, address?}`; you become the owner. `slug` is generated and never changes |
| GET / PATCH | `workshops/{id}/` | PATCH owner only; `status` may be `active` or `inactive` (`suspended` is staff-only) |
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

## Administration (`admin-api/`, staff only, otherwise 403)

`stats/`, `users/` (PATCH `is_active`, `is_staff`, `role`; cannot lock yourself out; only superusers change `is_staff`), `projects/`, `subscriptions/` (PATCH `plan_slug`), `payments/` (+ `POST {id}/confirm/` activates the plan, `{id}/reject/`), `logs/` (5xx errors), `features/` (CRUD flags), `broadcast/` (POST notification to all users), `storage/`.

### Audit log (`admin-api/audit-logs/`, platform admins only, read-only)

Append-only record of who did what: `actor`, `actor_email` (kept if the account is deleted), `action` (`create|update|delete|login|logout|password`), `event` (business event such as `order.status_changed`, empty for plain changes; filterable), `model` (`app.model`), `object_id`, `object_repr`, `changes` (`{field: {old, new}}` for updates), `ip`, `method`, `path`, `created_at`. Filters: `action`, `model`, `object_id`, `actor`, `actor_email`, `created_after`, `created_before`; `?search=` over email, object and path; paginated, newest first. Passwords and fields containing `password`/`token`/`secret`/`api_key` are stored as `[redacted]`; values over 200 characters are truncated. Create/update/delete are recorded automatically for users, folders, projects, materials, calculations, cutting lists, designs, gallery images, files, conversations, plans, subscriptions, payments, feature flags, **workshops, members, orders and tasks**. Workshop events: `workshop.created/updated/owner_changed/deleted`, `member.invited/accepted/declined/left/removed/role_changed`, `order.created/updated/status_changed/deleted`, `task.created/updated/assigned/status_changed/completed/deleted`. Customer phone, email and address are logged as `[redacted]` (the log shows *that* they changed, not their values). `QuerySet.update()`, `bulk_create()` and raw SQL do not send Django signals and are therefore not recorded automatically (cutting-list part replacement is recorded explicitly). Set `AUDIT_IP_HEADER=HTTP_X_REAL_IP` only behind a proxy that overwrites that header (docker-compose does); otherwise the IP is `REMOTE_ADDR`.
