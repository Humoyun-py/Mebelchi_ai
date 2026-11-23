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
| POST | `calculations/material/` | body: `width,height,depth,thickness=18,shelves=0,doors=0,drawers=0,back_thickness=4,material,back_material`; optional `save, name, project`. Returns `parts[], summary, hardware[], warnings[], assumptions[], requires_professional_review` |
| GET/DELETE | `calculations/`, `calculations/{id}/` | saved results |
| CRUD | `cutting-lists/` | `parts[]` are replaced as a whole on update |
| POST | `cutting-lists/from-calculation/` | cabinet fields + `name, project, sheet_length, sheet_width` |
| POST | `cutting-lists/{id}/optimize/` | `{allow_rotation}` → stored run: groups per material+thickness, sheets with placements, utilization, waste, leftover strip, estimated cost, `unplaced[]` |
| GET | `cutting-lists/{id}/runs/` | last 10 runs |
| GET | `cutting-lists/{id}/export/pdf/` `.../export/xlsx/` | throttled; counts toward the plan's monthly export limit |
| POST | `geometry/preview/` | same body as calculation (+ `color` as `#rrggbb`) → `{dimensions, boxes[], warnings}`. Public (stateless, anonymous throttle) |
| POST | `geometry/export/{glb|gltf|obj}/` | binary download; throttled |
| CRUD | `designs/` | `kind: furniture|interior`, free-form `config` (≤200 KB), optional `project`, `room_image` |

## Room design (`room-flows/`)

The guided room-design conversation, shared by the web app and the Telegram bot. Full description, rules, errors and the bot endpoints
(`telegram/bot/room-flows/...`): [ROOM_FLOW.md](ROOM_FLOW.md).

| Method | Path | Notes |
|---|---|---|
| POST | `room-flows/` | start a flow; returns `{id, status, step, descriptor, answers, rev, ...}` |
| GET | `room-flows/?status=active`, `room-flows/{id}/` | list and resume |
| POST | `room-flows/{id}/answer/` | `{step, value}`; wrong step 409 `step_mismatch`, bad value 400 |
| POST | `room-flows/{id}/back/ abandon/` | |
| GET | `room-flows/{id}/model/` | 3D boxes of the room and its furniture |
| POST | `room-flows/{id}/items/` | add furniture; `rev` required |
| PATCH/DELETE | `room-flows/{id}/items/{item_id}/` | change or remove; `rev` required, stale `rev` is 409 `rev_conflict` |

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

## Administration (`admin-api/`, staff only, otherwise 403)

`stats/`, `users/` (PATCH `is_active`, `is_staff`, `role`; cannot lock yourself out; only superusers change `is_staff`), `projects/`, `subscriptions/` (PATCH `plan_slug`), `payments/` (+ `POST {id}/confirm/` activates the plan, `{id}/reject/`), `logs/` (5xx errors), `features/` (CRUD flags), `broadcast/` (POST notification to all users), `storage/`.
