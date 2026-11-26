/** Room designer: types of the /rooms API and the pure geometry the plan editor needs. Units are millimetres.
 *  The server is the authority for every rule; the helpers here only make the editor feel immediate (clamp, snap, hint). */
export type Wall = 'north' | 'east' | 'south' | 'west'
export type Rot = 0 | 90 | 180 | 270
export type Loc = Partial<Record<'en' | 'uz' | 'ru', string>>
export const WALLS: Wall[] = ['north', 'east', 'south', 'west']
export const ROTATIONS: Rot[] = [0, 90, 180, 270]
export const DOOR_ZONE = 800

export interface RoomSize { width: number; length: number; height: number }
export interface RoomOpening { type: 'door' | 'window'; wall: Wall; offset: number; width: number; height: number; sill: number }
export interface RoomItem { id: string; template: string; name: string; x: number; z: number; rot: Rot; width: number; depth: number; height: number; shelves: number; doors: number; drawers: number; color: string; thickness?: number }
export interface RoomWarning { code: string; item?: string; message: string }
export interface RoomConfig { schema: 'room.v1'; goal: string; style: string; room: RoomSize; openings: RoomOpening[]; items: RoomItem[]; not_placed: RoomWarning[]; colors: { wall: string; floor: string; item: string } }

export interface Option { id: string; label: Loc; text?: Loc; category?: string; furniture?: string; wall?: string }
export interface Field { key: string; type: 'number' | 'multi'; label: Loc; min?: number; max?: number; default?: number; options?: Option[] }
export interface CatalogEntry { slug: string; category: string; label: Loc; name: string; defaults: { width: number; height: number; depth: number } }
export type RoomStep = 'goal' | 'photo' | 'elements' | 'size' | 'openings' | 'style' | 'generate' | 'furnish' | 'done'
export interface Question {
  step: RoomStep; title: Loc; prompt: Loc; index: number; total: number; can_back: boolean; optional: boolean; kind: 'choice' | 'photo' | 'number_group' | 'openings' | 'summary' | 'furnish'
  value?: unknown; options?: Option[]; fields?: Field[]; unit?: string
  required?: { doors: number; windows: number }; walls?: { id: Wall; label: Loc }[]; wall_lengths?: Record<Wall, number>
  limits?: { door: { width: [number, number]; height: [number, number] }; window: { width: [number, number]; height: [number, number]; sill: [number, number] }; edge_margin: number; gap: number }
  catalog?: CatalogEntry[]; rotations?: Rot[]; max_items?: number; room?: RoomSize
}
export interface RoomFlow {
  id: number; status: 'active' | 'completed' | 'abandoned'; step: RoomStep; answers: Record<string, unknown>; question: Question; design: number | null
  room: { config: RoomConfig; warnings: RoomWarning[] } | null; created_at: string; updated_at: string; item?: RoomItem; item_warnings?: RoomWarning[]
}
export interface RoomBrief { id: number; status: RoomFlow['status']; step: RoomStep; goal: string | null; design: number | null; created_at: string; updated_at: string }
export interface RoomModel { dimensions: { width: number; depth: number; length: number; height: number; wall_thickness: number }; boxes: import('./types').Box[]; warnings: RoomWarning[] }

export type Rect = { x0: number; z0: number; x1: number; z1: number }

/** Footprint of an item after rotation (rot 90/270 swap width and depth). */
export function footprint(i: Pick<RoomItem, 'x' | 'z' | 'rot' | 'width' | 'depth'>): Rect {
  const [w, d] = i.rot === 0 || i.rot === 180 ? [i.width, i.depth] : [i.depth, i.width]
  return { x0: i.x, z0: i.z, x1: i.x + w, z1: i.z + d }
}
export const overlaps = (a: Rect, b: Rect) => a.x0 < b.x1 && b.x0 < a.x1 && a.z0 < b.z1 && b.z0 < a.z1
export const snap = (v: number, step = 10) => Math.round(v / step) * step
export const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), Math.max(lo, hi))

/** Keeps the footprint inside the room (the server refuses anything outside). */
export function clampPosition(item: Pick<RoomItem, 'rot' | 'width' | 'depth'>, x: number, z: number, room: RoomSize): { x: number; z: number } {
  const f = footprint({ ...item, x: 0, z: 0 })
  return { x: clamp(x, 0, room.width - f.x1), z: clamp(z, 0, room.length - f.z1) }
}
export const overlapsAny = (item: RoomItem, others: RoomItem[]) => others.some((o) => o.id !== item.id && overlaps(footprint(item), footprint(o)))

/** The free area in front of each door that the server warns about when it is blocked. */
export function doorZones(room: RoomSize, openings: RoomOpening[]): Rect[] {
  return openings.filter((o) => o.type === 'door').map((o) => {
    const a0 = o.offset, a1 = o.offset + o.width, { width: W, length: L } = room
    return { north: { x0: a0, z0: 0, x1: a1, z1: DOOR_ZONE }, south: { x0: a0, z0: L - DOOR_ZONE, x1: a1, z1: L },
      west: { x0: 0, z0: a0, x1: DOOR_ZONE, z1: a1 }, east: { x0: W - DOOR_ZONE, z0: a0, x1: W, z1: a1 } }[o.wall]
  })
}

/** A door or window drawn as a thick bar on its wall line. */
export function openingRect(o: RoomOpening, room: RoomSize, thickness = 120): Rect {
  const a0 = o.offset, a1 = o.offset + o.width
  return { north: { x0: a0, z0: -thickness / 2, x1: a1, z1: thickness / 2 }, south: { x0: a0, z0: room.length - thickness / 2, x1: a1, z1: room.length + thickness / 2 },
    west: { x0: -thickness / 2, z0: a0, x1: thickness / 2, z1: a1 }, east: { x0: room.width - thickness / 2, z0: a0, x1: room.width + thickness / 2, z1: a1 } }[o.wall]
}

/** Cutaway for the 3D tab: without the ceiling and the two walls nearest the default camera (south and east) the furniture is visible. */
export const cutawayBoxes = (boxes: import('./types').Box[]) => boxes.filter((b) => b.kind !== 'ceiling' && !/^Wall (south|east)\b/.test(b.name))

export const nextRotation = (r: Rot): Rot => ((r + 90) % 360) as Rot
export const wallLength = (room: RoomSize, wall: Wall) => (wall === 'north' || wall === 'south' ? room.width : room.length)

/** Starting values for the openings form: spread over the walls so the first suggestion is already valid for a typical room. */
export function defaultOpenings(required: { doors: number; windows: number }, room: RoomSize): RoomOpening[] {
  const out: RoomOpening[] = []
  for (let i = 0; i < required.doors; i++) out.push({ type: 'door', wall: i % 2 ? 'south' : 'north', offset: 500, width: 900, height: 2100, sill: 0 })
  for (let i = 0; i < required.windows; i++) {
    const wall: Wall = i % 2 ? 'west' : 'east'
    out.push({ type: 'window', wall, offset: Math.min(800 + 1500 * Math.floor(i / 2), Math.max(100, wallLength(room, wall) - 1300)), width: 1200, height: 1200, sill: 900 })
  }
  return out
}

/** Localised wall/option labels arrive as {en,uz,ru}; the same helper formats a size for display. */
export const fmtM = (mm: number) => `${(mm / 1000).toFixed(mm % 100 === 0 ? 1 : 2)} m`
