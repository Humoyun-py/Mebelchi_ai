/** Types and pure helpers for the guided room design. The geometry mirrors backend/apps/geometry/room.py, so what the
 *  plan shows (footprints, clamping, opening defaults) matches what the server accepts. Sizes are millimetres. */
import type { Box } from './types'

export type L3 = Partial<Record<'en' | 'uz' | 'ru', string>>
export type Wall = 'north' | 'east' | 'south' | 'west'
export type Rot = 0 | 90 | 180 | 270

export const WALLS: Wall[] = ['north', 'east', 'south', 'west']
export const ROTATIONS: Rot[] = [0, 90, 180, 270]
export const DOOR_ZONE = 800
export const DOOR_DEFAULT = { width: 900, height: 2100 }
export const WINDOW_DEFAULT = { width: 1200, height: 1200, sill: 900 }
export const EDGE_MARGIN = 100
export const CEILING_MARGIN = 100

export interface Room { width: number; length: number; height: number }
export interface Opening { id?: string; type: 'door' | 'window'; wall: Wall; offset: number; width: number; height: number; sill: number }
export interface RoomItem {
  id: string; template: string; name: string; x: number; z: number; rot: Rot; width: number; depth: number; height: number
  shelves: number; doors: number; drawers: number; color: string; thickness?: number
}
export interface RoomWarning { code: string; message?: string; item?: string }

export interface DescriptorField {
  key: string; type: 'number' | 'multi'; label: L3; min?: number; max?: number; default?: number
  options?: { id: string; label: L3; category?: string }[]
}
export interface Descriptor {
  step: string; kind: 'choice' | 'photo' | 'number_group' | 'openings' | 'furnish' | 'summary'
  title: L3; prompt: L3; index: number; total: number; can_back: boolean; optional: boolean; value: unknown
  options?: { id: string; label: L3; text?: L3; furniture?: string; wall?: string }[]
  fields?: DescriptorField[]; unit?: string
  required?: { doors: number; windows: number }; room?: Partial<Room>; walls?: { id: Wall; label: L3 }[]
  limits?: { door: { width: [number, number]; height: [number, number] }; window: { width: [number, number]; height: [number, number]; sill: [number, number] } }
  wall_lengths?: Record<Wall, number>
  catalog?: { slug: string; category: string; label: L3; name: string; defaults: Record<string, number> }[]
}
export interface FlowView {
  id: number; status: 'active' | 'completed' | 'abandoned'; step: string; descriptor: Descriptor; answers: Record<string, unknown>
  design_id: number | null; photo_id: number | null; rev: number | null; warnings: RoomWarning[]
  items?: RoomItem[]; openings?: Opening[]; room?: Room; style?: string; created_at: string; updated_at: string
}
export interface FlowSummary { id: number; status: string; step: string; design: number | null; photo: number | null; created_at: string; updated_at: string }
export interface RoomModel {
  rev: number; goal: string; style: string; room: Room; openings: Opening[]; items: RoomItem[]; boxes: Box[]; warnings: RoomWarning[]
  dimensions: { width: number; depth: number; length: number; height: number }; requires_professional_review: boolean; disclaimer: string
}
export interface ItemResult { rev: number; item?: RoomItem; items: RoomItem[]; warnings: RoomWarning[] }

// ------------------------------------------------------------------------------------------------ geometry

export type Rect = [number, number, number, number]  // x0, z0, x1, z1

/** Footprint after rotation: a quarter turn swaps width and depth. */
export function footprint(i: Pick<RoomItem, 'x' | 'z' | 'rot' | 'width' | 'depth'>): Rect {
  const [w, d] = i.rot === 0 || i.rot === 180 ? [i.width, i.depth] : [i.depth, i.width]
  return [i.x, i.z, i.x + w, i.z + d]
}
export const overlaps = (a: Rect, b: Rect) => a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3]
export const snap = (v: number, step = 50) => Math.round(v / step) * step

/** Keep an item's footprint inside the room (the server rejects anything outside). */
export function clampPosition(i: Pick<RoomItem, 'rot' | 'width' | 'depth'>, x: number, z: number, room: Room) {
  const [x0, z0, x1, z1] = footprint({ ...i, x: 0, z: 0 })
  return { x: Math.min(Math.max(0, x), Math.max(0, room.width - (x1 - x0))), z: Math.min(Math.max(0, z), Math.max(0, room.length - (z1 - z0))) }
}

export const wallLength = (room: Room, wall: Wall) => (wall === 'north' || wall === 'south' ? room.width : room.length)

/** The strip an opening covers on the plan, in room coordinates (x0, z0, x1, z1), drawn on the wall line. */
export function openingRect(o: Opening, room: Room): Rect {
  const a0 = o.offset, a1 = o.offset + o.width
  return { north: [a0, 0, a1, 0], south: [a0, room.length, a1, room.length], west: [0, a0, 0, a1], east: [room.width, a0, room.width, a1] }[o.wall] as Rect
}

/** Area in front of a door that furniture should leave free (a warning on the server, not an error). */
export function doorZones(room: Room, openings: Opening[]): Rect[] {
  return openings.filter((o) => o.type === 'door').map((o) => {
    const a0 = o.offset, a1 = o.offset + o.width
    return { north: [a0, 0, a1, DOOR_ZONE], south: [a0, room.length - DOOR_ZONE, a1, room.length], west: [0, a0, DOOR_ZONE, a1], east: [room.width - DOOR_ZONE, a0, room.width, a1] }[o.wall] as Rect
  })
}

/** Sensible starting values for an opening so the form never starts invalid: heights stay clear of the ceiling. */
export function defaultOpening(type: 'door' | 'window', wall: Wall, room: Room): Opening {
  const top = room.height - CEILING_MARGIN
  if (type === 'door') return { type, wall, offset: EDGE_MARGIN, width: DOOR_DEFAULT.width, height: Math.min(DOOR_DEFAULT.height, top), sill: 0 }
  return { type, wall, offset: EDGE_MARGIN, width: WINDOW_DEFAULT.width, height: Math.min(WINDOW_DEFAULT.height, top - WINDOW_DEFAULT.sill), sill: WINDOW_DEFAULT.sill }
}

/** Direction an item faces, as a unit vector in plan coordinates (x east, z south). Rot 0 faces +z. */
export const FRONT: Record<Rot, [number, number]> = { 0: [0, 1], 90: [1, 0], 180: [0, -1], 270: [-1, 0] }

export const nextRot = (r: Rot): Rot => ((r + 90) % 360) as Rot

/** Server-side warnings as readable text keys. */
export function warningKey(w: RoomWarning): string | null {
  return { door_zone: 'rf.warnDoor', not_placed: 'rf.warnNotPlaced', items_reset: 'rf.warnReset' }[w.code] ?? null
}

/** Replaces {name} placeholders in a translated text. */
export const fill = (s: string, vars: Record<string, string | number>) => s.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? ''))
