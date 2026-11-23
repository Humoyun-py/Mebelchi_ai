export type Role = 'maker' | 'homeowner'
export interface User {
  id: number; email: string; first_name: string; last_name: string; full_name: string; phone: string
  avatar_url: string | null; role: Role; role_selected: boolean; theme: 'dark' | 'light'; language: 'en' | 'uz' | 'ru'
  notify_email: boolean; notify_system: boolean; is_admin: boolean; date_joined: string
}
export interface Page<T> { count: number; next: string | null; previous: string | null; results: T[] }
export interface Project {
  id: number; name: string; description: string; category: string; status: 'active' | 'archived'; pinned: boolean
  folder: number | null; width: number | null; height: number | null; depth: number | null; thickness: string | null
  material: number | null; params: Record<string, unknown>; counts: Record<string, number>; created_at: string; updated_at: string
}
export interface Folder { id: number; name: string; parent: number | null; project_count: number }
export interface CabinetInput {
  width: number; height: number; depth: number; thickness: number; shelves: number; doors: number; drawers: number
  back_thickness?: number; material?: string; back_material?: string
}
export interface CalcPart {
  name: string; width: number; height: number; thickness: number; quantity: number; material: string
  can_rotate: boolean; edge_w: number; edge_h: number; edge_note: string; area_m2: number; edge_length_mm: number
}
export interface CalcResult {
  input: CabinetInput; parts: CalcPart[]; warnings: string[]; assumptions: string[]; disclaimer: string; saved_id?: number
  requires_professional_review: boolean
  hardware?: { name: string; quantity: number; note: string }[]
  summary: { panel_count: number; distinct_parts: number; total_area_m2: number; edge_banding_m: number; waste_factor_assumed: number
    by_material: Record<string, { material: string; thickness: number; area_m2: number; parts: number; estimated_area_with_waste_m2: number }> }
}
export interface Box { name: string; kind: string; x: number; y: number; z: number; sx: number; sy: number; sz: number; color: string }
export interface GeometryResult { dimensions: { width: number; height: number; depth: number; thickness: number }; boxes: Box[]; warnings: string[] }
export interface CuttingPart {
  id?: number; name: string; width: number | string; height: number | string; thickness: number | string; quantity: number
  material: string; can_rotate: boolean; edge_w: number; edge_h: number; edge_note: string
}
export interface CuttingList {
  id: number; name: string; project: number | null; sheet_length: number; sheet_width: number; kerf: string; trim: string
  parts: CuttingPart[]; totals: { pieces: number; area_m2: number; edge_banding_m: number }
  latest_run: { id: number; sheet_count: number; utilization_pct: number; created_at: string } | null; updated_at: string
}
export interface Placement { part_id: number; name: string; x: number; y: number; w: number; h: number; rotated: boolean; color?: string }
export interface OptSheet { index: number; placements: Placement[]; used_area_mm2: number; utilization_pct: number }
export interface OptGroup {
  key: string; material: string; thickness: number; price_per_sheet: number | null; estimated_cost: number | null
  result: { sheet: { length: number; width: number; kerf: number; trim: number }; sheets: OptSheet[]; legend?: { name: string; color: string; quantity: number; width: number; height: number }[]
    summary: { sheet_count: number; utilization_pct: number; waste_pct: number; waste_area_m2: number; last_sheet_offcut: { width: number; area_m2: number } | null } }
}
export interface OptRun {
  id: number; sheet_count: number; utilization_pct: number; created_at: string
  result: { groups: OptGroup[]; unplaced: { name: string; width: number; height: number }[]
    summary: { sheet_count: number; utilization_pct: number; waste_pct: number; estimated_cost: number | null; unplaced_count: number }; disclaimer?: string }
}
export interface Material { id: number; name: string; kind: string; thickness: string; sheet_length: number; sheet_width: number; price_per_sheet: string | null; color: string; is_system: boolean }
export interface Template { id: number; slug: string; category: string; name: string; description: string; defaults: CabinetInput }
export interface GalleryImage { id: number; name: string; source: string; favorite: boolean; project: number | null; url: string; width: number; height: number; size_bytes: number; created_at: string }
export interface UserFile { id: number; name: string; kind: string; size_bytes: number; project: number | null; url: string; created_at: string }
export interface Design { id: number; name: string; kind: 'furniture' | 'interior'; project: number | null; config: Record<string, unknown>; room_image: number | null; updated_at: string }
export interface Conversation { id: number; title: string; project: number | null; message_count: number; updated_at: string }
export interface ChatMessage {
  id: number; role: 'user' | 'assistant'; content: string; attachments: { type: string; id: number; name: string }[]
  metadata: { intent?: string; input?: CabinetInput; actions?: { type: string; label: string }[] }; feedback: '' | 'like' | 'dislike'; created_at: string
}
export interface Notification { id: number; title: string; body: string; level: 'info' | 'success' | 'warning'; read: boolean; created_at: string }
export interface Plan { slug: string; name: string; price_usd: string; storage_mb: number; max_projects: number; max_exports_per_month: number; features: string[] }
export interface Usage {
  plan: { slug: string; name: string; price_usd: string; features: string[] }; status: string
  projects: { used: number; limit: number | null }; exports_this_month: { used: number; limit: number | null }
  storage: { used_bytes: number; limit_bytes: number; percent: number; images: number; files: number }
  payments: { id: number; plan: string; amount: string; status: string; created_at: string }[]
}
export interface WorkspaceSummary { projects: number; archived: number; pinned: number; folders: number; calculations: number; cutting_lists: number; designs: number; images: number; files: number; conversations: number; models_3d: number }

export type LText = Record<'en' | 'uz' | 'ru', string>
export interface Meta {
  limits: Record<string, [number, number]>; defaults: Record<string, number>
  project_categories: { value: string; label: LText }[]; furniture_categories: { slug: string; label: LText }[]
  boards: { value: string; label: LText }[]
  rooms: { id: string; label: LText; categories: string[] }[]; styles: { id: string; label: LText; text: LText; furniture: string; wall: string }[]
  showcase: { name: LText; input: CabinetInput; color: string }[]; export_formats: string[]
  stats: { key: string; value: number; label: LText; hint: LText }[]
  content: { features: { icon: string; title: LText; text: LText }[]; steps: { icon: string; title: LText; text: LText }[]; faq: { q: LText; a: LText }[] }
}
