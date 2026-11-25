# MEBELCHI AI

Furniture design, calculation and production-preparation platform. Two experiences: **Furniture Maker** (calculator, cutting lists, sheet optimizer, 3D editor, exports) and **Home Owner** (interior designer, room photos, parametric furniture).

**No external AI is used anywhere.** There are no calls to OpenAI, Anthropic, Google, Hugging Face or any other AI service. All logic is deterministic Python: panel formulas, guillotine sheet packing, parametric 3D geometry, GLB/glTF/OBJ writers, and a rule-based chat command parser. The chat assistant is *not* a language model and says so; unsupported requests get an honest limitation message. `apps/calculations/engine.py`, `apps/cutting_lists/optimizer.py` and `apps/geometry/builder.py` are the seams where trained models can be added later behind the same interfaces.

```
React SPA (Vite, TS, Tailwind, R3F)  --REST/JWT-->  Nginx --> Django REST --> PostgreSQL
                                                                      \--> Redis --> Celery (worker + beat)
```

## Repository layout

| Path | Contents |
|---|---|
| `backend/` | Django 6 + DRF. 17 apps under `backend/apps/` (accounts, users, workspaces, projects, materials, furniture, calculations, cutting_lists, geometry, designs, conversations, galleries, files, subscriptions, notifications, analytics, core) |
| `frontend/` | React 19 + TypeScript + Vite + Tailwind 4, Zustand, TanStack Query, Axios, Framer Motion, React Three Fiber |
| `deploy/` | PostgreSQL backup script |
| `docs/` | `ARCHITECTURE.md`, `API.md`, `DEPLOYMENT.md`, `openapi.yaml` (generated) |
| `docker-compose.yml` | db, redis, backend, worker, beat, web (nginx), backup |

## Quick start (development)

Requirements: Python 3.12+, Node 20+ (tested on 24). PostgreSQL and Redis are optional in development: without `POSTGRES_DB` the backend uses SQLite, and without `REDIS_URL` Celery tasks run in-process.

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
echo "DJANGO_DEBUG=true" > .env
python manage.py migrate          # also seeds plans, materials, furniture templates, feature flags
python manage.py createsuperuser  # optional: gives access to the Administration section
python manage.py runserver        # http://localhost:8000  (API docs: /api/v1/docs/)

# frontend (new terminal)
cd frontend
npm install
npm run dev                       # http://localhost:5173, /api is proxied to :8000
```

Password-reset emails print to the backend console in development.

## Run with Docker

```bash
cp .env.example .env     # then replace every CHANGE value
docker compose up -d --build
```

The site is served by Nginx on `WEB_PORT` (default 80). See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for TLS, backups, restore and hardening notes.

## Tests

```bash
cd backend  && python manage.py test apps     # 350 tests: engine, cabinet types, pricing, optimizer verification, geometry, auth, isolation, uploads, admin, audit, workshops (permissions, orders, tasks, query counts, statistics), chat, tasks
cd frontend && npm test                       # 120 tests: API error handling, i18n (parity and key coverage), brand contrast, formatting, UI components, workshop/order/task screens, calculator request contract, admin audit tab
cd frontend && npx tsc -b && npm run build    # type-check and production build
```

The backend suite also passes against PostgreSQL 16 (set `POSTGRES_*` variables). The suite is the safety net for the rules that matter most: every object is only reachable by its owner (other users get 404), uploads are validated by content, signed file links are bound to one file, admin endpoints reject non-staff, and users cannot escalate privileges through their profile.

## Features

- **Auth**: register (two-step, password strength meter), **Google sign-in** (set `GOOGLE_CLIENT_ID` in `backend/.env`; without it the button explains it is not configured), JWT login with rotating refresh tokens (blacklisted on logout), password reset (no account enumeration), change password, session list and revocation, role selection stored in the database.
- **Material calculator**: width/height/depth/thickness/shelves/doors/drawers to a full parts list (size, quantity, material, edge banding), area, edge-banding length, estimated hardware counts, warnings, and the written assumptions behind every formula. Hard validation of ranges and impossible geometry. Cabinet types (standard, kitchen base with plinth, kitchen wall, sliding wardrobe), edge-tape thickness with cut sizes, and an optional price estimate built only from prices you supply or your own material catalogue (missing prices are reported, never guessed).. The calculator page has a cabinet-type selector, edge-tape thickness, a cut-size column and a **Price** tab (you type the prices, the server does the arithmetic; empty prices are reported as missing).
- **Cutting lists**: generate from a calculation or build manually, edit, save; **PDF** and **Excel** export stamped "for professional review".
- **Material optimizer**: guillotine shelf packing with kerf, edge trim, grain-aware rotation, six sort strategies plus seeded random-order trials (bounded by job size; never worse than the fixed strategies, saved a sheet in about 4% of random benchmark jobs); reports utilization, waste, leftover strip, estimated cost (when sheet prices are set) and any part too large for the sheet. SVG sheet layouts in the UI and PDF.
- **3D**: parametric model built from the same parameters as the calculator; orbit/zoom/pan, dimension annotations, colors, wireframe, 2D front elevation, export **GLB / glTF / OBJ**.
- **Chat assistant** (rule-based): answers in the language you write (Uzbek, Russian, English), handles greetings and small talk, markdown, tables, copy/edit/regenerate/like/dislike/delete/export, attachments, voice input.
- **Home owner**: interior designer with room photo, style presets, furniture options, dimensions, wall placement and a top-down room plan with fit warnings.
- **Workshops** (screens under *Workshops* in the sidebar): workshops with owner and employees (invitations, soft removal, ownership transfer), customer orders with a guarded status lifecycle, payment records, status history, production tasks with assignment and employee status updates, owner statistics. Strict per-workshop isolation; employees never see order prices. Status buttons are drawn from `allowed_next_statuses` sent by the server, so the lifecycle rules live only in the backend. See `docs/API.md` and `docs/ARCHITECTURE.md`.
- **Audit log**: append-only record of who created, changed or deleted what (admin API `admin-api/audit-logs/` and the **Audit log** tab of the Administration page, with filters).
- **Projects, folders, gallery (masonry, lightbox, favorites, search), files, notifications, subscriptions, settings (7 sections), admin dashboard.**
- Dark (default) and light themes saved to the profile; English, Uzbek, Russian; responsive from phone to desktop.

## Known limitations (read before relying on it)

- **Output is not verified for manufacture.** Formulas use documented assumptions (overlay back, 20 mm shelf setback, drawer slide clearances, etc.). Hardware (hinges, slides, handles, shelf pins, confirmats, back fixings) is only a rule-of-thumb quantity estimate shown next to each calculation; it is not manufacturer data and no hardware drilling or placement is modelled. Every export says it needs professional review.
- **No image, drawing or sketch understanding.** "Analyze Drawing", "Read Hand Sketch" and room photos store the files and attach them to projects; dimensions are entered manually. This is stated in the UI.
- **Payments are records only.** There is no payment gateway. Requesting a paid plan creates a pending payment that an administrator confirms in the admin panel. Plan prices and limits are illustrative and editable.
- **Voice input** uses the browser's built-in speech recognition (with a one-time disclosure), which in some browsers is processed by the browser vendor.
- **Translations**: navigation, sidebar, core actions, the calculator and cutting-list screens are translated to Uzbek and Russian; backend-generated warnings/assumptions and long-form pages are English only. Uzbek and Russian strings should be reviewed by a native speaker.
- Landing-page statistics are platform capabilities (counts of tools, formats and categories), not customer numbers. Privacy Policy and Terms pages are templates that need legal review. The Contact footer link appears only when `VITE_CONTACT_EMAIL` is set at build time.
- Auth tokens are kept in `localStorage` (standard SPA trade-off; mitigated by a strict CSP in the Nginx config, short access-token lifetime and refresh rotation).
- The optimizer is a fast heuristic (guillotine shelf packing), not a provably optimal solver.
- 3D models are assembled from boxes (panels), not detailed hardware or moulded parts.

## Security summary

JWT with rotation and blacklist; PBKDF2 hashing and Django password validators; per-object ownership filtering on every query; content-checked uploads (extension, size, real image decode, PDF signature); private files only via short-lived signed links (`/media` is never exposed); throttling (anonymous, user, auth, export); CORS allow-list; production settings enforce a secret key, HTTPS redirect, HSTS and secure cookies; Nginx adds CSP, `X-Frame-Options`, `nosniff`; nightly `pg_dump` backups with 14-day retention. `manage.py check --deploy` is clean apart from the optional HSTS-preload flag.
# Mebelchi_ai
