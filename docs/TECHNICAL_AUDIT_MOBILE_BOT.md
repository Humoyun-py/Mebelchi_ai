# Technical Audit: Flutter app and Telegram bot (Phase 1)

Date: 2026-11-27. Branch: `integrate/remote-main`. Read-only audit; no code was changed. Basis: repository files, README/docs, `urls.py` and models. Tests were not re-run in this audit.

## 1. Summary
The backend already covers most of what mobile and the bot need: JWT auth, roles, projects, calculator, cutting lists, room designer (`.mebelchi` export/import, GLB), furniture catalogue with approval, workshops/orders, marketplace matching, commission and manual payments, Telegram linking. **Missing**: any Flutter code, real AI chat, room-photo analysis, the Mebelchi client (CRM) module, deep-link order delivery, SMS/phone verification in the API surface, the APK download/release system, and a bot that covers more than calculator/projects/files.

## 2. What exists (by requested area)
| Area | State |
|---|---|
| Auth | `auth/register|login|refresh|logout|password-reset|password-change`, SimpleJWT with rotation + blacklist, session list, Google sign-in. Phone verification (Eskiz SMS, `PhoneVerification`) written but **uncommitted** |
| Roles | `maker`, `homeowner`, `workshop` (admin-assigned) + staff/superuser. Workshops start `pending` until admin approval |
| Projects/files | `projects`, `folders`, `gallery`, `files` (signed private links), `designs` |
| Calculator / cutting list | `calculations/material`, `cutting-lists/` (+optimize, PDF/XLSX) |
| Room designer | `rooms/` (create, items add/patch/delete, reset-layout, settings, export `.mebelchi`, import, export-glb, import-design) |
| 3D format | Server-built box geometry; GLB/glTF/OBJ exporters; room config schema `room.v1` |
| Catalogue | `furniture/templates` with price, workshop, status/approval, 6-side images, GLB upload/export, duplicate check |
| Marketplace | `marketplace/match`, `marketplace/orders` (place, follow, cancel, reroute, pay, rate); deterministic matching (price 35, distance 20, rating 20, lead 15, load 10); reminders via Celery beat (15 min, max 6) |
| Finance | `PlatformSettings` (commission, default 20%), `OrderPayment` (manual confirm), refunds, report; Payme provider + `PaymentTransaction` + webhook (uncommitted); Click/Uzum are empty stubs |
| AI | `apps/ai`: provider abstraction, disabled by default; OpenAI/Anthropic adapters (uncommitted, never run against live APIs); only endpoint is `ai/status/` |
| Telegram | `telegram_bot/` (aiogram 3, no DB): link by code, projects, calculator, cutting list, files, notifications, admin commands; `integrations` app exposes `telegram/bot/*` endpoints |
| Audit/security | Append-only audit log, per-owner querysets (404 on foreign), throttles, content-checked uploads, signed file URLs |
| CI | PostgreSQL 16 + SQLite backend jobs, frontend, bot, image build, backup/restore checks |

## 3. Gaps against the specification
| # | Gap | Needs |
|---|---|---|
| 1 | No Flutter project (Flutter and an Android SDK folder are installed locally; APK signing key and a device/emulator are not confirmed) | Phase 2 |
| 2 | **Real AI chat**: `conversations` is a rule-based parser; the AI layer has no chat endpoint, no memory, no image input route | AI provider + key from the owner |
| 3 | **Room-photo analysis** (walls, doors, windows, furniture, sizes) needs a vision model; README/roadmap say photos are stored only | same as 2; must label estimates as estimates |
| 4 | Image-to-3D pipeline | no provider chosen; only GLB upload/import exists. Single-photo accurate 3D must not be promised |
| 5 | **Mebelchi client module** (name, phone, Telegram username, address, photos, notes; client projects) | new `clients` models, API, tests |
| 6 | Send project to client by Telegram / phone / link / app; deep link `t.me/<bot>?start=<token>`; shareable project link | new share-token model, bot start-payload handler |
| 7 | Bot flows for orders: workshop accept/reject buttons, customer address/location + two phones, 24 h contact message, re-routing | bot handlers + notification hooks (reminder logic already in backend) |
| 8 | Bot AI chat and photo handling | depends on 2 |
| 9 | Workshop registration fields (owner, working hours, delivery area, contract status, employee count) | partly in `Workshop` (coordinates, radius, categories, capacity, lead time); contract status and working hours need checking/adding |
| 10 | Order status set: spec lists New/Pending/Accepted/Rejected/In Production/Quality Check/Ready/Delivery/Completed/Cancelled. Backend has pending, rejected, quality_check, delivery, confirmed (=Accepted), delivered (=Completed); `Ready` and `In Production` mapping must be verified | small migration + mapping doc |
| 11 | Price tiers minimum/average/premium exist over real quotes; no market-price source (correct: only admin/workshop prices) | none, keep |
| 12 | Payments: Payme written (uncommitted), Click and Uzum not implemented (protocol unverified), no real split/escrow/payout; payouts to workshops not modelled | provider contracts, legal review |
| 13 | Admin panel items: AI usage (`AIUsage` model exists, UI no), complaints, contracts, reports; web catalogue approval UI | web work |
| 14 | APK download page, release automation, version history, checksum | Phase 9 |
| 15 | Mobile 3D room editor with first-person walk | web has top-down plan + 3D view; no walkthrough yet |
| 16 | OpenAPI exists (`docs/openapi.yaml`) but must be regenerated for the uncommitted endpoints | each phase |
| 17 | README is stale (17 apps, 388 tests, "no AI") | docs |

## 4. Conflict to resolve
Earlier decisions said no external AI; on 2026-11-25 the owner chose a real provider layer. The provider and API key are still not supplied, so items 2, 3, 4, 8 cannot be delivered or tested end to end yet. Until then the app must show "AI is not configured" and never fake output.

## 5. Proposed order (needs approval, one phase at a time)
0. Review and commit the uncommitted provider work (AI adapters, Eskiz, phone verification, Payme), after running the full test suite on SQLite and PostgreSQL.
1. Phase 2 Flutter foundation (Riverpod, Dio, secure token storage, role-based navigation) against the existing API.
2. Backend additions as each phase needs them: clients, share/deep-link tokens, `ai` chat endpoints, order-status mapping.
3. Later phases as listed in the specification.

## 6. Decisions needed from the owner
1. AI provider and key (OpenAI or Anthropic), and the model name.
2. State management: Riverpod (recommended) or BLoC.
3. Are the uncommitted files to be committed first? Is committing/pushing allowed?
4. Payment provider order (Payme first, since written) and legal entity/contract status.
5. Android signing: who creates the keystore (kept outside the repo)?
6. Telegram bot username and token (kept in `.env`).
