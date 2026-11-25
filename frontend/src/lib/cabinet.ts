import type { CabinetInput, CabinetType } from './types'

/** Cabinet type and its type-specific settings. These are *inputs*; every formula stays on the server. */
export interface TypeState { cabinet_type: CabinetType; edge_thickness: number; plinth_height: number; sliding_overlap: number; track_top: number; track_bottom: number; rail_width: number }
export const DEFAULT_TYPE: TypeState = { cabinet_type: 'standard', edge_thickness: 0, plinth_height: 100, sliding_overlap: 30, track_top: 35, track_bottom: 20, rail_width: 100 }
export const CABINET_TYPES: CabinetType[] = ['standard', 'kitchen_base', 'kitchen_wall', 'sliding_wardrobe']
/** Convenient starting sizes when the user picks a type (a starting point only; the server validates what is actually sent). */
export const TYPE_PRESETS: Partial<Record<CabinetType, Partial<CabinetInput>>> = {
  kitchen_base: { width: 600, height: 720, depth: 560, thickness: 18, shelves: 1, doors: 1, drawers: 0 },
  kitchen_wall: { width: 800, height: 720, depth: 320, thickness: 18, shelves: 1, doors: 2, drawers: 0 },
  sliding_wardrobe: { width: 1800, height: 2300, depth: 600, thickness: 18, shelves: 2, doors: 3, drawers: 0 },
}
