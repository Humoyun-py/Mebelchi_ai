import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { api } from '../../lib/api'
import type { CalcResult, PriceLine } from '../../lib/types'
import { httpError, page, renderApp, routeGet, signIn } from '../../test/utils'
import Calculator from './Calculator'

vi.mock('../../lib/api', async (orig) => ({ ...(await orig<typeof import('../../lib/api')>()), api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() }, downloadBlob: vi.fn() }))
vi.mock('../../components/three/LazyViewer', () => ({ CabinetViewer: () => <div data-testid="viewer" /> }))

const part = (name: string, w: number, h: number, extra = {}) => ({ name, width: w, height: h, thickness: 18, quantity: 1, material: 'MDF', can_rotate: false, edge_w: 1, edge_h: 0, edge_note: 'front edge', area_m2: 0.1, edge_length_mm: 800, ...extra })
const line = (o: Partial<PriceLine>): PriceLine => ({ category: 'board', item: 'MDF 18 mm', quantity: 5, unit: 'm2', unit_price: null, amount: null, note: '', ...o })
const result = (req: Record<string, unknown>, over: Partial<CalcResult> = {}): CalcResult => ({
  input: req as never, parts: [part('Side panel', 400, 2000, { cut_width: 399.2, cut_height: 2000 })], warnings: [], assumptions: ['Overlay back panel.'], disclaimer: 'For professional review.', requires_professional_review: true,
  hardware: [{ name: 'Hinge', quantity: 4, note: '' }], summary: { panel_count: 6, distinct_parts: 3, total_area_m2: 6.25, edge_banding_m: 17.39, edge_banding_thickness_mm: Number(req.edge_thickness ?? 0), waste_factor_assumed: 0.15,
    by_material: { 'MDF 18 mm': { material: 'MDF', thickness: 18, area_m2: 4.66, parts: 5, estimated_area_with_waste_m2: 5.36 }, 'HDF 4 mm': { material: 'HDF', thickness: 4, area_m2: 1.59, parts: 1, estimated_area_with_waste_m2: 1.83 } } }, ...over })

let calls: Record<string, unknown>[] = []
const lastCalc = () => calls[calls.length - 1]
beforeEach(() => {
  vi.clearAllMocks(); signIn(); calls = []
  routeGet({ '/meta/': { limits: { width: [200, 4000], height: [200, 3000], depth: [150, 1000], thickness: [8, 40], shelves: [0, 20], doors: [0, 6], drawers: [0, 10] }, boards: [{ value: 'MDF', label: { en: 'MDF', uz: 'MDF', ru: 'МДФ' } }] }, '/projects/': page([]) })
  vi.mocked(api.post).mockImplementation(async (_u: string, body: unknown) => { const b = body as Record<string, unknown>; calls.push(b); return { data: result(b) } as never })
})
const pick = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } })
const settled = () => waitFor(() => expect(calls.length).toBeGreaterThan(0))

describe('Calculator: request contract with the backend', () => {
  it('a plain calculation sends no price block and the old defaults (backward compatible)', async () => {
    renderApp(<Calculator />); await settled()
    expect(lastCalc()).toMatchObject({ width: 800, height: 2000, depth: 400, thickness: 18, shelves: 3, doors: 2, drawers: 0, material: 'MDF', cabinet_type: 'standard', edge_thickness: 0 })
    expect(lastCalc()).not.toHaveProperty('prices'); expect(lastCalc()).not.toHaveProperty('use_catalog_prices')
    expect(await screen.findByText('6.25 m2')).toBeInTheDocument()
  })

  it('choosing a cabinet type sends it, applies a sensible starting size and shows only that type\'s settings', async () => {
    renderApp(<Calculator />); await settled()
    expect(screen.queryByLabelText('Top track')).not.toBeInTheDocument(); expect(screen.queryByLabelText('Plinth height')).not.toBeInTheDocument()
    pick('Cabinet type', 'sliding_wardrobe')
    await waitFor(() => expect(lastCalc()).toMatchObject({ cabinet_type: 'sliding_wardrobe', width: 1800, height: 2300, depth: 600, doors: 3, drawers: 0, sliding_overlap: 30, track_top: 35, track_bottom: 20 }))
    expect(screen.getByLabelText('Top track')).toBeInTheDocument(); expect(screen.getByLabelText('Panel overlap')).toBeInTheDocument(); expect(screen.getByText(/at least 2/)).toBeInTheDocument()
    pick('Cabinet type', 'kitchen_base')
    await waitFor(() => expect(lastCalc()).toMatchObject({ cabinet_type: 'kitchen_base', width: 600, height: 720, depth: 560, doors: 1 }))
    expect(screen.getByLabelText('Plinth height')).toBeInTheDocument(); expect(screen.queryByLabelText('Top track')).not.toBeInTheDocument()
    pick('Cabinet type', 'kitchen_wall')
    await waitFor(() => expect(lastCalc()).toMatchObject({ cabinet_type: 'kitchen_wall', depth: 320, drawers: 0 })); expect(screen.getByLabelText('Rail width')).toBeInTheDocument()
  })

  it('edge tape thickness is sent and the parts table gains a cut-size column only then', async () => {
    renderApp(<Calculator />); await settled()
    expect(screen.queryByRole('columnheader', { name: 'Cut size' })).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Edge tape thickness'), { target: { value: '0.8' } })
    await waitFor(() => expect(lastCalc()).toMatchObject({ edge_thickness: 0.8 }))
    expect(await screen.findByRole('columnheader', { name: 'Cut size' })).toBeInTheDocument(); expect(screen.getByText('399.2 x 2000')).toBeInTheDocument(); expect(screen.getByText('tape 0.8 mm')).toBeInTheDocument()
  })

  it('invalid numbers stop the request instead of sending NaN', async () => {
    renderApp(<Calculator />); await settled(); const n = calls.length
    fireEvent.change(screen.getByLabelText('Edge tape thickness'), { target: { value: '' } })
    await new Promise((r) => setTimeout(r, 450)); expect(calls.length).toBe(n); expect(screen.getAllByText('Required').length).toBeGreaterThan(0)
  })

  it('shows the server\'s validation error for the offending field', async () => {
    vi.mocked(api.post).mockRejectedValue(httpError(400, { error: { status: 400, detail: 'Validation failed.', fields: { doors: ['a sliding wardrobe needs at least 2 sliding doors'] } } }))
    renderApp(<Calculator />)
    expect((await screen.findAllByText('a sliding wardrobe needs at least 2 sliding doors')).length).toBeGreaterThan(0)
  })
})

describe('Calculator: price estimate', () => {
  const openPrices = async () => { renderApp(<Calculator />); await settled(); fireEvent.click(await screen.findByRole('tab', { name: 'Price' })) }

  it('asks for a price before showing anything and sends nothing priced until the user types a price', async () => {
    await openPrices()
    expect(screen.getByText('Enter at least one price to see the estimate.')).toBeInTheDocument(); expect(lastCalc()).not.toHaveProperty('prices')
    expect(screen.getByLabelText('MDF 18 mm')).toBeInTheDocument(); expect(screen.getByLabelText('HDF 4 mm')).toBeInTheDocument(); expect(screen.getByLabelText(/Hinge x4/)).toBeInTheDocument()   // one input per real board and hardware line
  })

  it('typed prices go into the request; empty ones are left out so they come back as missing', async () => {
    await openPrices()
    fireEvent.change(screen.getByLabelText('MDF 18 mm'), { target: { value: '95000' } }); fireEvent.change(screen.getByLabelText(/Hinge/), { target: { value: '1 200,5' } })
    fireEvent.change(screen.getByLabelText('Markup'), { target: { value: '20' } }); fireEvent.change(screen.getByLabelText('Currency'), { target: { value: 'UZS' } })
    await waitFor(() => expect(lastCalc()).toHaveProperty('prices'))
    expect(lastCalc().prices).toEqual({ currency: 'UZS', board_price_per_m2: { 'MDF 18': 95000 }, hardware_prices: { Hinge: 1200.5 }, waste_factor: 0.15, markup_pct: 20 })
    expect(lastCalc().use_catalog_prices).toBe(false)
  })

  it('renders the server\'s breakdown, flags missing prices and never adds a total of its own', async () => {
    vi.mocked(api.post).mockImplementation(async (_u: string, body: unknown) => { const b = body as Record<string, unknown>; calls.push(b); return { data: result(b, { pricing: {
      currency: 'UZS', complete: false, missing: ['board: HDF 4 mm', 'labor: Manufacturing labour'], subtotals: { board: 442000, edge_banding: 0, hardware: 4802, labor: 0 }, manufacturing_cost: 446802, markup_pct: 20, markup_amount: 89360.4, total_price: 536162.4, basis: '',
      lines: [line({ item: 'MDF 18 mm', unit_price: 95000, amount: 442000 }), line({ item: 'HDF 4 mm' }), line({ category: 'hardware', item: 'Hinge', quantity: 4, unit: 'pcs', unit_price: 1200.5, amount: 4802 }), line({ category: 'labor', item: 'Manufacturing labour', unit: 'm2' })] } }) } as never })
    await openPrices(); fireEvent.change(screen.getByLabelText('MDF 18 mm'), { target: { value: '95000' } })
    expect(await screen.findByText('2 item(s) have no price. The totals below cover only the priced items.')).toBeInTheDocument()
    expect(screen.getAllByText('no price').length).toBe(2); expect(screen.getByText('Manufacturing cost')).toBeInTheDocument()
    expect(screen.getByText(`${(446802).toLocaleString()} UZS`)).toBeInTheDocument(); expect(screen.getByText(`${(536162.4).toLocaleString(undefined, { minimumFractionDigits: 2 })} UZS`)).toBeInTheDocument(); expect(screen.getByText('Markup 20%')).toBeInTheDocument()
  })

  it('"use my saved material prices" asks the server for catalogue prices', async () => {
    await openPrices(); fireEvent.click(screen.getByRole('switch', { name: 'Use my saved material prices' }))
    await waitFor(() => expect(lastCalc()).toMatchObject({ use_catalog_prices: true, prices: expect.any(Object) }))
  })

  it('saving and creating a cutting list keep the same inputs (and the price block when requested)', async () => {
    renderApp(<Calculator />); await settled()
    fireEvent.click(await screen.findByRole('button', { name: /Save/ }))
    await waitFor(() => expect(calls.some((c) => c.save === true)).toBe(true))
    expect(calls.find((c) => c.save === true)).toMatchObject({ cabinet_type: 'standard', width: 800, name: 'Cabinet 800x2000x400' })
  })
})

describe('Calculator: tabs', () => {
  it('the 3D tab still loads a preview from the same inputs', async () => {
    vi.mocked(api.post).mockImplementation(async (u: string, body: unknown) => { const b = body as Record<string, unknown>; if (u.includes('geometry')) { calls.push({ ...b, __geometry: true }); return { data: { dimensions: { width: 800, height: 2000, depth: 400, thickness: 18 }, boxes: [], warnings: [] } } as never } calls.push(b); return { data: result(b) } as never })
    renderApp(<Calculator />); await settled(); const tab = within(screen.getByRole('tablist')).getByRole('tab', { name: /3D/ }); fireEvent.click(tab)
    expect(await screen.findByTestId('viewer')).toBeInTheDocument(); expect(calls.find((c) => c.__geometry)).toMatchObject({ cabinet_type: 'standard', width: 800 })
  })
})
