# Phase 2A: backend foundation for mobile, Telegram and the marketplace

Everything here is backend only. No payment provider, AI provider, SMS or push service is connected; nothing was deployed.

## Decisions (from the owner)
AI: provider-agnostic layer, disabled without a key, no fake answers. Payments: full records and a 20% (configurable) commission, manual admin confirmation, no real money movement. SMS and push: not integrated, architecture ready. Coordinates entered by hand, distance by Haversine. Prices only from admin or workshop input. `.mebelchi` is not DRM.

## What was added
| Area | Where |
|---|---|
| AI layer, SMS interface | `apps/ai/providers.py` (`get_provider()` returns the disabled provider until a provider + key are configured), `apps/core/sms.py` |
| Catalogue | `apps/furniture`: price/workshop/status/material/colour/lead time/GLB on `FurnitureTemplate`, `FurnitureImage` (6 sides), CRUD, duplicate check, approval, GLB import/export |
| `.mebelchi` | `apps/rooms/mebelchi.py`, `rooms/export`, `rooms/import`, `rooms/settings`, `rooms/export-glb` |
| Workshop profile | `apps/workshops`: coordinates, radius, categories, capacity, availability, lead time, price list, transport, assembly, rating (`WorkshopReview`) |
| Order statuses | `pending`, `rejected`, `quality_check`, `delivery` added; `confirmed` = Accepted, `delivered` = Completed (values kept for compatibility) |
| Pricing and matching | `apps/marketplace/pricing.py` (over the engine's `price_estimate`), `matching.py`, min/average/premium over real quotes |
| Customer API | `/marketplace/` (match, place, follow, cancel, reroute, pay, rate) |
| Finance | `apps/finance`: `PlatformSettings` (commission), `OrderPayment`, manual confirmation, refunds, report |
| Reminders | `apps/marketplace/tasks.py`, beat every 15 min |

Migrations: `furniture 0003`, `workshops 0004`, `finance 0001`. All additive; existing rows get safe defaults (platform templates stay `approved`).

## Behaviour worth knowing
- Existing `furniture/templates/` clients keep working (plain array). The old "read only" test was replaced: writing now needs a workshop or staff (403/400 otherwise).
- Room designer only offers approved, active items.
- Money: Decimals, half-up to the cent, commission snapshot per order, split always sums to the total.
- Reminders: one conditional UPDATE claims each reminder, so concurrent workers cannot send the same one twice; they stop when the order leaves `pending`; after the 6th the customer and admins are told once.
- Rejected order: reason required; the customer is notified and can see alternatives and re-route (a workshop that already refused is never offered).

## Limits (not done on purpose)
No real payment/escrow/split; no SMS or push; matching distance is straight-line; the AI layer has no provider adapter yet; one piece of furniture per marketplace order; ratings are per order, customers cannot edit them; workshop capacity is checked at placement, not locked (two simultaneous orders can exceed it by one).
