# MEBELCHI AI — Architecture

No external AI services are used anywhere. All "intelligence" is deterministic
Python: parametric furniture generation, 2D bin-packing, rule-based chat
commands. The chat engine is a command/rule parser and says so honestly.
`apps/geometry` and `apps/calculations/engine` are the seams where trained
models can be plugged in later behind the same service interfaces.

## Topology

```
Browser (React SPA) --/api/v1--> Nginx --> Gunicorn (Django + DRF) --> PostgreSQL
                                                     \--> Redis --> Celery worker (exports, cleanup)
                         /media/ served by Nginx (private files go through authenticated API)
```

Frontend and backend are separate applications; the only contract is REST + JWT.

## Backend apps (`backend/apps/`)

| App | Responsibility |
|---|---|
| core | shared permissions, pagination, throttles, upload validators, base viewsets |
| accounts | register, login (JWT), logout (blacklist), password reset/change |
| users | `User` model (email login, role, theme, language), profile, role selection, sessions |
| workspaces | `Folder` (nested), per-user workspace summary |
| projects | `Project`, `ProjectActivity`; duplicate/archive/pin |
| materials | `Material` (system + user), seeded catalogue |
| furniture | `FurnitureTemplate` (category presets used by the editors) |
| calculations | pure engine (`engine.py`: parts, validation), `Calculation` records |
| cutting_lists | `CuttingList`, `CuttingPart`, `OptimizationRun`; optimizer (`optimizer.py`); PDF/XLSX export |
| geometry | parametric box-model builder (`builder.py`) and room model (`room.py`: validation, walls with openings, furniture placement, layout suggestion); GLB / glTF / OBJ exporters |
| designs | `Design` (furniture + interior configuration) |
| conversations | `Conversation`, `Message`; rule-based command engine (`assistant.py`) and the room-design state machine (`flow.py`) |
| rooms | `RoomFlow` (conversation state per owner); services shared by the web and bot endpoints; the room itself lives in `Design.config` (`room.v1`). See `docs/ROOM_FLOW.md` |
| galleries | `GalleryImage` (upload, favorite, rename, search) |
| files | `UserFile` (PDF/drawings/documents), storage accounting |
| subscriptions | `Plan`, `Subscription`, `Payment` (records only, no payment gateway) |
| notifications | `Notification` |
| analytics | `UsageEvent`, `SystemLog`; admin dashboard stats; feature flags |

Each app: `models.py`, `serializers.py`, `views.py`, `urls.py`, `services.py`
(where logic exists), `permissions.py` (core re-exports), `tests/`.

## Key relationships

- `User 1—* Project`, `Project *—1 Folder(null)`, `Project *—1 Material(null)`
- `Project 1—* Calculation | CuttingList | Design | GalleryImage | UserFile | Conversation`
- `CuttingList 1—* CuttingPart`, `CuttingList 1—* OptimizationRun`
- `Conversation 1—* Message`
- `User 1—1 Subscription *—1 Plan`, `Subscription 1—* Payment`
- Every user-owned table has `owner` FK; every viewset filters by `owner=request.user`
  (admins have a separate `/admin-api/` surface). Cross-user access returns 404.

## REST API (`/api/v1/`)

```
auth/register  auth/login  auth/refresh  auth/logout
auth/password-reset  auth/password-reset/confirm  auth/password-change
users/me (GET/PATCH)  users/me/role  users/me/avatar  users/me/sessions  users/me/storage
folders/  projects/ (+ /{id}/duplicate /archive /unarchive /pin /activity)
materials/  furniture/templates/  furniture/categories/
calculations/material (POST, stateless)  calculations/ (saved records)
cutting-lists/ (+ /generate /optimize /export/pdf /export/xlsx)
geometry/preview (POST)  geometry/export/{glb|gltf|obj} (POST)
designs/
conversations/ (+ /{id}/messages)
room-flows/ (+ /{id}/answer /back /abandon /model /items/{item_id})
gallery/ (+ /{id}/favorite)   files/
subscriptions/plans  subscriptions/me  subscriptions/upgrade
notifications/ (+ /{id}/read /read-all)
analytics/me
admin-api/stats users/ projects/ subscriptions/ payments/ logs/ features/ storage/
schema/  docs/   (OpenAPI via drf-spectacular)
```

## Engineering rules baked into the engine

- All dimensions are millimetres, validated against explicit min/max.
- Cabinet panel formulas use documented assumptions (returned in every result
  under `assumptions`); results carry `requires_professional_review: true`
  and exports are stamped "For professional review — not verified for manufacture".
- Hardware (`hardware` in the result) is a rule-of-thumb estimate: hinges by door height/width,
  one slide pair and handle per drawer front, 4 shelf pins per shelf, confirmats per carcass joint,
  back-panel fixings at ~200 mm pitch. It is not manufacturer data.
- Optimizer: guillotine shelf packing with kerf, grain-aware rotation, several
  sort strategies, picks best by (sheets, waste). Oversized parts are reported,
  never silently dropped.

## Frontend (`frontend/`)

React + TS + Vite + Tailwind (CSS-variable design tokens, dark default),
Zustand (auth/theme/UI), TanStack Query (server state), Axios (JWT refresh
interceptor), Framer Motion, React Router, R3F for 3D.

```
src/pages/{landing,auth,app,admin}   route-level screens
src/components/ui                    shared primitives (Button, Card, Modal, Tabs, ...)
src/components/three                 R3F viewer (canvas-sprite labels, no drei <Html>)
src/layouts                          AppShell, RightPanel
src/hooks/queries.ts                 TanStack Query hooks
src/stores                           Zustand: auth, ui (theme, language)
src/lib                              api (Axios), i18n (en/uz/ru dictionaries), types, format
```

Translations live in `src/lib/i18n.ts`. A vitest parity test fails if `uz` or `ru`
lacks a key present in `en`.

## Phases

1. Foundation — backend skeleton, users/auth/roles, design system, landing
2. Core — dashboard shell, projects, chat, workspaces
3. Engine — calculator, cutting list, optimizer, 3D
4. Advanced — gallery/files, editor, interior, exports
5. Admin — dashboards, subscriptions, analytics
6. Production — tests, security, Docker, Nginx, docs
