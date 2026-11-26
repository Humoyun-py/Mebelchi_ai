# Phase 5.1: the old interior designer is replaced by the room designer

## Audit (before the change)
| Question | Finding |
|---|---|
| Where was `Interior.tsx` used? | `App.tsx` (lazy route `/app/interior`), nothing else imported it. |
| Links to it | `Home.tsx` (7 tiles: 3 rooms, 4 styles), `AppShell.tsx` (menu item for non-makers), `Designs.tsx` (open an interior design). |
| How old designs are stored | `Design(kind="interior")`, `config` = `{room, style, template, input{width,height,depth,thickness,shelves,doors,drawers}, color, wallColor, roomW, roomL, roomH, wall, align, notes}`; `room_image` = gallery photo. Saved with `POST/PATCH /designs/`. |
| Old open/edit/save | `/app/interior?design=<id>` loaded `GET /designs/<id>/`; the Save button PATCHed the same config. One cabinet against one wall, no openings. |
| Room designer storage | `RoomFlow` (conversation) one-to-one with `Design`; config `room.v1` (`schema`, `room`, `openings`, `items[]`, `not_placed`, `colors`). |
| Format difference | Yes: old = one cabinet positioned by `wall`+`align`; new = list of items with `x`, `z`, `rot` in mm. Not directly compatible, so an adapter is needed. |

## What changed
- **Backend** `apps/rooms/legacy.py` (pure adapter) and `services.import_legacy`, endpoint `POST /api/v1/rooms/import-design/` (see API.md).
  - The old design is **never modified or deleted**. The room designer works on a copy (same name, owner, project, photo); the old config is kept whole under `config.legacy`, the source id under `config.migrated_from`.
  - Idempotent: importing again (or importing the copy) returns the same flow; the first copy's edits are never overwritten. The source row is locked, so two concurrent imports create one copy.
  - Checked before converting: the design must be the caller's own `interior` design; the room must be inside the room designer's limits (width/length 1000-15000 mm, height 2000-4500 mm) otherwise 400 naming `roomW`/`roomL`/`roomH`; hex colours, style, room type and template are validated, unknown values fall back and are listed in `config.import_notes`. A cabinet that does not fit becomes a `not_placed` warning; the room is still imported.
  - Cabinet position is reproduced exactly as the old plan drew it (wall + alignment), rotated to face into the room.
  - No `input` in the old config means no cabinet is invented.
- **Frontend**
  - `/app/interior` stays valid: `?design=<id>` -> `/app/rooms/import/<id>`; `?room=kitchen|bedroom|living|office|wardrobe|other` -> `/app/rooms/new?goal=...`; anything else -> `/app/rooms`.
  - `/app/rooms/new?goal=` starts a design once (ref-guarded, replaces its own URL so reload never creates a second one).
  - `/app/rooms/import/:designId` shows a loading state, then the room designer, or the server's reason plus "Your original design is unchanged".
  - Home tiles, menu and Designs list now lead to the room designer. All routes stay inside the existing login guard.
  - `Interior.tsx` is **removed** (nothing else imported it; shared components it used, `CabinetViewer`, `Swatches`, `useGeometry`, are used elsewhere and kept).

## Known limits
- The four "style" tiles on Home open a fresh room designer; the wizard asks for the style at its own step, so the tile's style is not pre-selected.
- A design whose conversation was deleted (`RoomFlow` removed, `Design` kept) has a `room.v1` config but no conversation; opening it from Designs shows the 409 message. Not part of this change.
- The old designer's cabinet-only "template" list is replaced by the room designer's catalogue; templates that no longer exist keep their sizes.
