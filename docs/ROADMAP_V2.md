# MEBELCHI AI: Roadmap v2 (customer journey, workshops, orders)

Status: decisions recorded (see "Decisions"). Phase 0 is in progress on feat/foundation-roles-audit.

## Ground rules
- No external AI APIs. Chat is a rule-based state machine.
- No scraping of third-party sites. Prices come from the internal catalog and approved sources.
- Every user sees only their own data. Roles are checked on every endpoint.
- No direct push to main. One branch per phase. PR only when requested.
- Production calculations are marked "for professional review".

## Real constraints (decided, not negotiable)
- Telegram bots can message a user only after that user has pressed /start. Phone numbers and usernames cannot be used for bot messages. Use a deep link: t.me/<bot>?start=<token>.
- A downloaded GLB can be opened by any 3D viewer. Blocking it is impossible.
- The .mbl format is NOT real protection. The web viewer needs the key in the browser, so an account holder can extract it. .mbl is a license and privacy layer (account-bound license, visible to the user), not DRM. The UI must say so.
- v1 does not analyse room photos (that needs computer vision). Photos are stored as reference; dimensions are entered manually.
- There is no payment gateway yet. Click/Payme (or another) needs a contract and legal review.
- Escrow (holding the customer's money until delivery) may require a license in some jurisdictions. Legal review is required before Phase 6. This plan does not replace legal advice.
- The contract text is a template and must pass legal review before use.

## Roles
Stored values in the codebase: maker (furniture master), homeowner (customer), workshop (new), plus admin via is_staff and is_superuser.
The names home_owner and furniture_maker in older drafts are the same concepts; the code keeps maker and homeowner.
Users cannot self-assign the workshop role. An administrator assigns it, and every change is audited.
A workshop becomes active only after onboarding and admin approval.

## Data model decision: one Workshop model
Individual masters and workshops share one model: Workshop with kind = individual | workshop. Both use the same order flow, so two models would duplicate code.

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

## Decisions
Recorded from the product owner's review. Items marked "recommendation" were accepted as proposed.
1. Commission base: product price after discounts, excluding delivery. On partial refund, commission is refunded proportionally. (Accepted.)
2. "More than 50 workshops": the platform offers up to 3 options built from budget, city, lead time and capacity. The customer chooses. Ratings need a review model, which is a later phase. (Accepted.)
3. Prices: entered by administrators and approved workshops. CSV import is admin-only. (Accepted.)
4. .mbl: opened only by the MEBELCHI viewer, with the license and privacy limits above. (Accepted.)
5. Room photo analysis with ML: postponed. Photos are stored only. (Accepted.)
6. Payment provider and legal entity: OPEN. Build the adapter and sandbox first; the real provider is chosen later. Phase 6 needs this answer before production.
7. One Workshop model with kind field. (Accepted.)
8. Work starts from origin/main. Existing feature branches are merged in main already. (Accepted.)

Ledger amounts: integers in minor units. Commission basis points (2000 = 20%), commission = (amount * bp + 5000) // 10000 (half-up), workshop share = amount - commission, so totals never drift. Ledger entries are append-only with an idempotency key per entry.

Order states: draft, sent, accepted_by_workshop, paid, in_production, delivered, completed, cancelled, disputed. Allowed transitions and the role allowed for each are kept in one place and tested.

## Open questions (answer before Phase 1)
1. Which payment provider (Click, Payme, other)? Is there a legal entity and a contract template?
2. Is the 20% commission on the gross amount, or after refunds and discounts?
3. What does "more than 50 workshops" mean exactly: number of options shown, ranking, or automatic choice?
4. Who enters prices: admin, workshop, or file import?
5. .mbl: only MEBELCHI viewer, or can other apps open it?
6. Room photo analysis (ML): postpone to a later phase?
