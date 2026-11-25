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
| geometry | parametric box-model builder; GLB / glTF / OBJ exporters |
| designs | `Design` (furniture + interior configuration) |
| conversations | `Conversation`, `Message`; rule-based command engine |
| galleries | `GalleryImage` (upload, favorite, rename, search) |
| files | `UserFile` (PDF/drawings/documents), storage accounting |
| subscriptions | `Plan`, `Subscription`, `Payment` (records only, no payment gateway) |
| notifications | `Notification` |
| analytics | `UsageEvent`, `SystemLog`; admin dashboard stats; feature flags |
| workshops | `Workshop`, `WorkshopMember`, `Order`, `Task` (+ status histories); permissions, lifecycle rules, statistics |
| audit | `AuditLog` (append-only: actor, action, object, field changes, IP); signal-based recording; admin read API |

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
gallery/ (+ /{id}/favorite)   files/
subscriptions/plans  subscriptions/me  subscriptions/upgrade
notifications/ (+ /{id}/read /read-all)
workshops/ (+ /{id}/members/ /{id}/members/{mid}/ /{id}/statistics/ /{id}/logo/)  workshop-invitations/  orders/  tasks/
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
  never silently dropped. Every result is verified by an independent routine
  (bounds, overlap, kerf clearance, each piece once, rotation rules) and is
  labelled approximate, not optimal.
- Cabinet types: `standard`, `kitchen_base` (plinth, rails, legs), `kitchen_wall`
  (hanging rail, brackets), `sliding_wardrobe` (two alternating lanes, tracks,
  rollers). The 3D builder reads the same `layout()` so model and parts agree.
- Edge banding thickness produces cut sizes (finished size minus one tape per banded edge).
- Pricing is pure arithmetic over caller-supplied prices; missing prices are
  reported, never defaulted.
- Audit: `AuditContextMiddleware` exposes the request (user, IP); signals on the
  tracked models write `AuditLog` rows in the same transaction; auth events are
  recorded explicitly.

## Workshops (Phase 3)

`apps/workshops` is the tenant layer for real furniture workshops. Models:

```
User 1-* WorkshopMember *-1 Workshop            (role owner|employee, status invited|active|removed; unique per user+workshop)
Workshop 1-* Order        (PROTECT)  1-* OrderStatusChange     (append-only history)
Workshop 1-* Task         (PROTECT)  1-* TaskStatusChange      (append-only history)
Order 1-* Task            (CASCADE; a task may also exist without an order)
Order *-1 WorkshopMember (assigned_employee, SET_NULL)   Task *-1 WorkshopMember (assigned_to, SET_NULL)
Order *-1 Project (related_project, SET_NULL)            Order *-1 User (created_by, customer_user, SET_NULL)
```

Design decisions:

- **People on orders/tasks are `WorkshopMember` rows, not users.** "Assigned to" therefore always means "a member of this workshop", and when an employee leaves the row stays (`status=removed`), so historical orders and tasks keep a valid reference. Nothing is deleted when somebody leaves.
- **Business records are protected.** `Order.workshop` and `Task.workshop` are `PROTECT`; a workshop with records can only be deactivated. Orders can be deleted only while `new`/`cancelled` and unpaid. Users who authored records are kept as `SET_NULL`.
- **Database constraints** carry the invariants that can be expressed per row or per workshop: one membership per (workshop, user); at most one owner row per workshop and the owner row must be active; `0 <= paid_amount <= total_price`; `deadline >= start_date`; unique `order_number`. Cross-row rules (a task's order and assignee belong to the task's workshop, valid status transitions, who may do what) live in `services.py` and are covered by tests; multi-step changes (create workshop + owner row, order + history, status change + task cancellation, ownership transfer) run in one transaction.
- **Permissions are centralised** in `workshops/access.py` (visibility querysets, owner checks, writable checks) and `services.py` (rules). Related-object ids in request bodies are validated against what the caller may see, so an id that does not exist and an id of somebody else's object give the same error. Employees' serializers drop money fields.
- **Order numbers** come from a per-workshop counter incremented by one atomic `UPDATE` (verified with 8 concurrent writers on PostgreSQL: 80 orders, no duplicates).
- **Audit**: every workshop model is in the audit signal registry; services label their saves with an event name (`order.status_changed`, ...). Customer contact details are redacted from the log.
- **Statistics** are database aggregates (`Count(filter=...)`, `Sum`) over the workshop's rows.

### Where the commercial modules plug in

Phase 3 deliberately stores only what it needs. The planned modules attach without rewriting these tables:

| Future module | Attach point | Migration path |
|---|---|---|
| CRM (customers, contact history) | `Order.customer_*` columns (+ optional `customer_user`) | add `Customer(workshop, ...)` and `Order.customer` FK; backfill from the columns with a data migration; keep columns until the UI switches |
| Production stages, quality control | `Task` (assignee, status, deadlines, history) and `Order` | add `ProductionStage(order, ...)`; tasks gain an optional stage FK |
| Inventory | `Workshop` as owner of stock | `InventoryItem/Movement(workshop, ...)`; link movements to `Order`/`Task` for consumption |
| Employee profiles, KPI | `WorkshopMember` (one row per person per workshop) | profile/KPI tables keyed by `member`; KPIs derive from `TaskStatusChange` |
| Finance, payments | `Order.total_price/paid_amount` | `Payment(order, amount, method, ...)` rows replace the manual `paid_amount`; the order amount becomes a cached sum; `Expense(workshop, ...)` for costs |
| Notifications | existing `notifications.notify()` (used now for invitations and task assignment) | add event hooks keyed by the audit event names |
| Order documents, approvals | `Order` | `OrderDocument` FK; approvals as new status history rows |

Not decided yet and intentionally left open: per-plan limits for workshops/members (the subscription layer can enforce them in `services.create_workshop` / `invite_member`), fine-grained employee permissions beyond owner/employee, and a staff view of workshops in the admin dashboard (Phase 8; for now staff use the Django admin, which is also where a workshop is suspended).

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

## Frontend: workshops, calculator and admin (Phase 4)

- **Screens**: `pages/app/Workshops.tsx` (list, create, my invitations), `pages/app/WorkshopDetail.tsx` (tabs by role: owner sees Overview/Orders/Tasks/Team/Settings, employees Orders/Tasks/Team; `?tab=` deep links never open owner-only tabs for employees). Tab bodies live in `components/workshop/`. The calculator gained cabinet types, edge tape, cut sizes and a Price tab (`components/PricingPanel.tsx`, `lib/cabinet.ts`); the optimizer result shows *Layout verified* and *Approximate result*; the Administration page has an **Audit log** tab.
- **No business rules in the UI**: status buttons come from the server's `allowed_next_statuses`; money, statistics and totals are rendered from API values; price inputs are sent as typed and empty ones are *omitted* so the server reports them as missing; the cabinet-type size presets are only starting values that the server validates.
- **Data freshness**: workshop queries (`hooks/workshops.ts`) always refetch on mount and window focus and poll every minute, because other people change shared data. (A real bug found by the end-to-end run: with the app-wide 15 s `staleTime` an employee kept seeing an empty order list after the owner created and assigned an order.)
- **Dialogs** (`components/ui/Modal.tsx`) render in a portal, only the innermost dialog reacts to Escape, scroll lock lasts until the last one closes, and autofocus never steals focus from a field the user already chose.
- **Responsive**: tables on workshop screens use `DataTable compact` and repeat status/number inside the title cell on phones; verified at 390 px with no horizontal overflow.
- **Brand**: design tokens in `index.css` use Deep Navy `#0F172A`, Cyan `#22D3EE` and white (dark theme); the light theme uses a darker cyan so text keeps WCAG AA contrast. `lib/brand.test.ts` checks the contrast ratios.
- **i18n**: English, Uzbek (Latin) and Russian; `i18n.parity.test.ts` and `i18n.coverage.test.ts` fail on missing keys or placeholders. Uzbek/Russian strings for the new screens should be reviewed by a native speaker.

## Phases

1. Foundation — backend skeleton, users/auth/roles, design system, landing
2. Core — dashboard shell, projects, chat, workspaces
3. Engine — calculator, cutting list, optimizer, 3D
4. Advanced — gallery/files, editor, interior, exports
5. Admin — dashboards, subscriptions, analytics
6. Production — tests, security, Docker, Nginx, docs
