import type { CabinetInput, ColorGroup, Colors, DesignConfig } from './types'
import { DEFAULT_TYPE } from './cabinet'

export const COLOR_GROUPS: ColorGroup[] = ['carcass', 'fronts', 'back', 'handle']
export const DEFAULT_COLORS: Record<ColorGroup, string> = { carcass: '#c9a27a', fronts: '#b98f63', back: '#8a7560', handle: '#9ca3af' }
/** Which colour group a drawn component belongs to (mirrors the server so the panel can show the right swatch). */
export const GROUP_OF_KIND: Record<string, ColorGroup> = { carcass: 'carcass', shelf: 'carcass', door: 'fronts', drawer: 'fronts', back: 'back', handle: 'handle' }
export const SCHEMA_VERSION = 1

export const BASE_INPUT: CabinetInput = { width: 800, height: 2000, depth: 400, thickness: 18, shelves: 3, doors: 2, drawers: 0, back_thickness: 4, material: 'MDF', back_material: 'HDF', handle_style: 'bar', ...DEFAULT_TYPE }
const NUMERIC: (keyof CabinetInput)[] = ['width', 'height', 'depth', 'thickness', 'shelves', 'doors', 'drawers', 'back_thickness', 'edge_thickness', 'plinth_height', 'sliding_overlap', 'track_top', 'track_bottom', 'rail_width']

export interface EditorDoc { name: string; input: CabinetInput; colors: Colors; materialId: string; projectId: string }
export const newDoc = (over: Partial<EditorDoc> = {}): EditorDoc => ({ name: 'Untitled design', input: { ...BASE_INPUT }, colors: {}, materialId: '', projectId: '', ...over })

/** Every numeric field holds a finite number (an empty input field is NaN while the user types; nothing is sent then). */
export const isValidInput = (i: CabinetInput) => NUMERIC.every((k) => i[k] === undefined || Number.isFinite(i[k] as number))

export function cleanColors(c: Colors): Colors {
  return Object.fromEntries(COLOR_GROUPS.filter((g) => c[g]).map((g) => [g, c[g]!.toLowerCase()])) as Colors
}

/** Body for the geometry preview/export endpoints. */
export const geometryBody = (d: EditorDoc): CabinetInput => ({ ...d.input, colors: cleanColors(d.colors) })

/** What gets stored. `color` is the carcass colour for readers of older designs. */
export function toConfig(d: EditorDoc): DesignConfig {
  const colors = cleanColors(d.colors)
  return { schema_version: SCHEMA_VERSION, input: d.input, color: colors.carcass ?? DEFAULT_COLORS.carcass, colors, material: d.materialId ? Number(d.materialId) : null }
}

/** Reads any stored design: new (colors map) and old (single colour, seven numbers). Missing fields take the defaults. */
export function fromConfig(config: DesignConfig | undefined, name: string, projectId: number | null): EditorDoc {
  const c = config ?? {}
  const colors: Colors = c.colors && Object.keys(c.colors).length ? cleanColors(c.colors) : c.color ? { carcass: c.color.toLowerCase(), fronts: c.color.toLowerCase() } : {}
  return { name, input: { ...BASE_INPUT, ...(c.input ?? {}) }, colors, materialId: c.material ? String(c.material) : '', projectId: projectId ? String(projectId) : '' }
}

/** Stable text of everything that is saved; two docs are "the same" exactly when their snapshots are equal. */
export const snapshot = (d: EditorDoc) => JSON.stringify([d.name.trim(), toConfig(d), d.projectId])
