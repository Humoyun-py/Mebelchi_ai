import { screen } from '@testing-library/react'
import type { CuttingList, OptRun } from '../../lib/types'
import { page, renderApp, routeGet, signIn } from '../../test/utils'
import CuttingLists from './CuttingLists'

vi.mock('../../lib/api', async (orig) => ({ ...(await orig<typeof import('../../lib/api')>()), api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() }, downloadBlob: vi.fn() }))
beforeEach(() => { vi.clearAllMocks(); signIn() })

const list: CuttingList = { id: 1, name: 'Wardrobe', project: null, sheet_length: 2800, sheet_width: 2070, kerf: '3.0', trim: '10.0', parts: [{ id: 1, name: 'Side', width: 400, height: 2000, thickness: 18, quantity: 2, material: 'MDF', can_rotate: false, edge_w: 0, edge_h: 1, edge_note: '' }],
  totals: { pieces: 2, area_m2: 1.6, edge_banding_m: 4 }, latest_run: { id: 5, sheet_count: 1, utilization_pct: 30, created_at: '2026-03-01T00:00:00Z' }, updated_at: '2026-03-01T00:00:00Z' }
const run = (extra: object): OptRun => ({ id: 5, sheet_count: 1, utilization_pct: 30, created_at: '2026-03-01T00:00:00Z', result: { unplaced: [], summary: { sheet_count: 1, utilization_pct: 30, waste_pct: 70, estimated_cost: null, unplaced_count: 0 },
  groups: [{ key: 'MDF 18 mm', material: 'MDF', thickness: 18, price_per_sheet: null, estimated_cost: null, result: { sheet: { length: 2800, width: 2070, kerf: 3, trim: 10 }, sheets: [{ index: 1, placements: [{ part_id: 1, name: 'Side', x: 0, y: 0, w: 2000, h: 400, rotated: false }], used_area_mm2: 1, utilization_pct: 30 }],
    summary: { sheet_count: 1, utilization_pct: 30, waste_pct: 70, waste_area_m2: 4, last_sheet_offcut: null } } }], ...extra } })
const open = (r: OptRun) => { routeGet({ '/cutting-lists/1/': list, '/cutting-lists/1/runs/': [r], '/cutting-lists/': page([list]) }); renderApp(<CuttingLists />, { path: '/app/cutting-lists/:id', url: '/app/cutting-lists/1' }) }

describe('optimizer result labelling', () => {
  it('says the layout is verified and approximate, in plain words', async () => {
    open(run({ approximate: true, is_optimal: false, validation: { valid: true } }))
    const note = await screen.findByRole('note')
    expect(note).toHaveTextContent('Layout verified'); expect(note).toHaveTextContent('Approximate result'); expect(note).toHaveTextContent('not guaranteed to use the fewest sheets possible')
  })
  it('does not claim verification for older stored runs that have no validation block', async () => {
    open(run({}))
    await screen.findAllByText('MDF 18 mm'); expect(screen.queryByRole('note')).not.toBeInTheDocument(); expect(screen.queryByText('Layout verified')).not.toBeInTheDocument()
  })
  it('a failed validation is never shown as verified', async () => {
    open(run({ approximate: true, validation: { valid: false } }))
    await screen.findByRole('note'); expect(screen.queryByText('Layout verified')).not.toBeInTheDocument(); expect(screen.getByText('Approximate result')).toBeInTheDocument()
  })
})
