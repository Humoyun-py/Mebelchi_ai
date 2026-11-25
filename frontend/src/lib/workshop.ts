import type { OrderStatus, PaymentStatus, PriceInput, TaskPriority, TaskStatus, WorkshopStatus } from './types'

export type Tone = 'neutral' | 'success' | 'warning' | 'danger' | 'primary'

export const ORDER_STATUSES: OrderStatus[] = ['new', 'confirmed', 'in_production', 'ready', 'delivered', 'cancelled']
export const PAYMENT_STATUSES: PaymentStatus[] = ['unpaid', 'partially_paid', 'paid', 'refunded']
export const TASK_STATUSES: TaskStatus[] = ['pending', 'in_progress', 'review', 'completed', 'cancelled']
export const TASK_PRIORITIES: TaskPriority[] = ['low', 'medium', 'high', 'urgent']

export const orderTone: Record<OrderStatus, Tone> = { new: 'neutral', confirmed: 'primary', in_production: 'warning', ready: 'primary', delivered: 'success', cancelled: 'danger' }
export const payTone: Record<PaymentStatus, Tone> = { unpaid: 'danger', partially_paid: 'warning', paid: 'success', refunded: 'neutral' }
export const taskTone: Record<TaskStatus, Tone> = { pending: 'neutral', in_progress: 'primary', review: 'warning', completed: 'success', cancelled: 'danger' }
export const priorityTone: Record<TaskPriority, Tone> = { low: 'neutral', medium: 'primary', high: 'warning', urgent: 'danger' }
export const workshopTone: Record<WorkshopStatus, Tone> = { active: 'success', inactive: 'neutral', suspended: 'danger' }

/** A text field that may hold a user-typed number: '' and non-numbers mean "not provided". Accepts a decimal comma. */
export function parseAmount(v: string): number | null {
  const s = v.trim().replace(/\s/g, '').replace(',', '.')
  if (!s) return null
  const n = Number(s)
  return Number.isFinite(n) && n >= 0 ? n : null
}

export interface PriceForm {
  currency: string; board: Record<string, string>; hardware: Record<string, string>; edge: string; labor: string; waste: string; markup: string
}
export const emptyPriceForm = (): PriceForm => ({ currency: '', board: {}, hardware: {}, edge: '', labor: '', waste: '15', markup: '' })

/** Turns what the user typed into the API payload. Empty fields are left out entirely, so they come back as "missing", never as 0. */
export function buildPrices(f: PriceForm): PriceInput {
  const map = (o: Record<string, string>) => Object.fromEntries(Object.entries(o).map(([k, v]) => [k, parseAmount(v)] as const).filter((e): e is [string, number] => e[1] !== null))
  const out: PriceInput = { currency: f.currency.trim().slice(0, 8), board_price_per_m2: map(f.board), hardware_prices: map(f.hardware) }
  const edge = parseAmount(f.edge), labor = parseAmount(f.labor), waste = parseAmount(f.waste), markup = parseAmount(f.markup)
  if (edge !== null) out.edge_price_per_m = edge
  if (labor !== null) out.labor_per_m2 = labor
  if (waste !== null) out.waste_factor = Math.min(waste, 60) / 100
  if (markup !== null) out.markup_pct = Math.min(markup, 300)
  return out
}

/** True when the form holds at least one price, i.e. a price estimate is worth requesting. */
export const hasAnyPrice = (f: PriceForm) =>
  Object.values(f.board).some((v) => parseAmount(v) !== null) || Object.values(f.hardware).some((v) => parseAmount(v) !== null) ||
  [f.edge, f.labor].some((v) => parseAmount(v) !== null)
