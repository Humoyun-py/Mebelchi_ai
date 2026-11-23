# MEBELCHI AI: Roadmap v2 (customer journey, workshops, orders)

Status: planned, not started. Start only after the open questions below are answered.

## Ground rules
- No external AI APIs. Chat is a rule-based state machine.
- No scraping of third-party sites. Prices come from the internal catalog and approved sources.
- Every user sees only their own data. Roles are checked on every endpoint.
- No direct push to main. One branch per phase. PR only when requested.
- Production calculations are marked "for professional review".

## Real constraints (decided, not negotiable)
- Telegram bots can message a user only after that user has pressed /start. Phone numbers and usernames cannot be used for bot messages. Use a deep link: t.me/<bot>?start=<token>.
- A downloaded GLB can be opened by any 3D viewer. "Opens only in MEBELCHI" is enforced with an encrypted .mbl format and an account-bound license, not by blocking GLB.
- v1 does not analyse room photos (that needs computer vision). Photos are stored as reference; dimensions are entered manually.
- There is no payment gateway yet. Click/Payme (or another) needs a contract and legal review.

## Roles
home_owner (customer), furniture_maker (master), workshop (new: furniture workshop), admin, super_admin.
A workshop becomes active only after onboarding and admin approval.

## Phase 1: Customer chat (web and bot share one state machine)
1. Goal: kitchen, bedroom, living room, wardrobe, office.
2. Optional room photo upload (stored, not analysed).
3. Room elements: walls, door, window, required furniture.
4. Room size in mm (min/max validation, impossible geometry rejected).
5. Style preset: modern, classic, minimal, luxury.
6. Generate 3D room with the deterministic geometry engine.
7. User places, rotates and resizes furniture. Positions are saved in the design.

## Phase 2: Walkthrough and export
- Web first-person camera (WASD + mouse) with wall and furniture collision.
- Design stored as versioned JSON.
- Export: encrypted .mbl (opens only in MEBELCHI web and mobile, bound to the account) and GLB (for viewing and export; the UI warns that GLB opens anywhere).

## Phase 3: Send to master
- Button "Ustaga yuborish" sends the design to a master or workshop.
- Channels: inside MEBELCHI (dashboard and notification), Telegram (deep link + /start), share link.
- Master can accept, ask a question, send a price, or decline.

## Phase 4: Pricing (internal catalog)
- Catalog of materials (board type, thickness, edge banding, hardware) with price, currency, date and source.
- Estimate = materials + labour fee + standard markup. Shown as "estimate" with date.
- Market prices only through admin entry or approved import. No scraping.

## Phase 5: Workshops
- Onboarding: registration, contract (template, legal review required), commission agreement, price list, lead time, capacity per month, city.
- Admin approves the profile.
- If there are 50 or fewer matching workshops: show all matches.
- If more than 50: ask the customer for a budget, then show up to 3 options (price, lead time, workshop) ranked by budget, city, capacity and rating. Thresholds are configurable.

## Phase 6: Orders, payment, split
- Customer chooses an option and accepts the order terms.
- Payment on web through a provider adapter (sandbox first).
- Split example: order 1000 USD -> platform 20% = 200 USD, workshop 80% = 800 USD.
- Ledger: append-only. Corrections are reversing entries. Amounts are integers in minor units.
- Funds go to the workshop after it confirms and the customer accepts (escrow logic).
- Order states: draft, sent, accepted_by_workshop, paid, in_production, delivered, completed, cancelled, disputed.

## Phase 7: Admin panel
- Dashboard: users, workshops, orders, payments, commission revenue, errors, system status.
- Workshop approval, suspension, contract status.
- Price catalog (CRUD with versions).
- Orders and disputes.
- Ledger and commission reports (export).
- Notifications and broadcast.
- Audit log of every admin change.

## Phase 8: Web and mobile
- Web: all flows above, using the existing design system (dark default, #2563EB, Inter).
- Mobile (Flutter): later. Keep the OpenAPI contract ready for it.

## Acceptance criteria
- Backend tests pass on PostgreSQL and SQLite. Permission tests: another user gets 404.
- Frontend: component and flow tests; npm run build succeeds.
- Bot: unit tests and an end-to-end run against a live backend on a separate port.
- Ledger test: 1000 USD order gives exactly 200 and 800.
- Each phase: its own branch, commit, and a report with real test results.

## Open questions (answer before Phase 1)
1. Which payment provider (Click, Payme, other)? Is there a legal entity and a contract template?
2. Is the 20% commission on the gross amount, or after refunds and discounts?
3. What does "more than 50 workshops" mean exactly: number of options shown, ranking, or automatic choice?
4. Who enters prices: admin, workshop, or file import?
5. .mbl: only MEBELCHI viewer, or can other apps open it?
6. Room photo analysis (ML): postpone to a later phase?
