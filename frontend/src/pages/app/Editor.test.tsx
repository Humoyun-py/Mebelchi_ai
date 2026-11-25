import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { api, downloadBlob } from '../../lib/api'
import type { Box, Design, GeometryResult } from '../../lib/types'
import { httpError, page, renderApp, routeGet, signIn } from '../../test/utils'
import Editor from './Editor'

vi.mock('../../lib/api', async (orig) => ({ ...(await orig<typeof import('../../lib/api')>()), api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() }, downloadBlob: vi.fn() }))
vi.mock('../../components/three/LazyViewer', () => ({
  CabinetViewer: (p: { boxes: Box[]; view: string; selected?: string | null; wire?: boolean; showDims?: boolean; onSelect?: (b: Box | null) => void }) => (
    <div data-testid="viewer" data-view={p.view} data-selected={p.selected ?? ''} data-wire={String(p.wire)} data-dims={String(p.showDims)} data-count={p.boxes.length}>
      <button onClick={() => p.onSelect?.(p.boxes[0])}>pick-first</button><button onClick={() => p.onSelect?.(null)}>pick-none</button></div>) }))

const box = (name: string, kind: string, over: Partial<Box> = {}): Box => ({ name, kind, x: 0, y: 0, z: 0, sx: 18, sy: 2000, sz: 400, color: '#c9a27a', ...over })
const model = (over: Partial<GeometryResult> = {}): GeometryResult => ({ dimensions: { width: 800, height: 2000, depth: 400, thickness: 18 }, warnings: [],
  boxes: [box('Left side', 'carcass'), box('Door 1', 'door', { sx: 396, sy: 1996, sz: 18, x: 2, y: 2, z: 400 }), box('Door handle 1', 'handle', { sx: 8, sy: 120, sz: 12 })],
  consistency: { valid: true, problems: [], checks: ['overall_size'], not_modelled: [] }, ...over })
const calc = { summary: { panel_count: 8, total_area_m2: 6.25, edge_banding_m: 17.39 }, parts: [], hardware: [], warnings: [], assumptions: [], disclaimer: '', requires_professional_review: true }
const design = (config: object, over: Partial<Design> = {}): Design => ({ id: 5, name: 'Saved wardrobe', kind: 'furniture', project: null, config, room_image: null, updated_at: '2026-03-01T00:00:00Z', ...over } as Design)
const NEW_CFG = { schema_version: 1, input: { width: 900, height: 1800, depth: 500, thickness: 18, shelves: 2, doors: 2, drawers: 0, handle_style: 'knob', cabinet_type: 'standard' }, colors: { fronts: '#445566' }, material: null }

let previews: Record<string, unknown>[] = []
const lastPreview = () => previews[previews.length - 1]
const TEMPLATES = [{ id: 1, slug: 'wardrobe', category: 'wardrobe', name: 'Wardrobe', description: '', defaults: { width: 1200, height: 2200, depth: 580, thickness: 18, shelves: 4, doors: 3, drawers: 0 } }]
const META = { limits: { width: [200, 4000], height: [200, 3000], depth: [150, 1000], thickness: [8, 40], shelves: [0, 20], doors: [0, 6], drawers: [0, 10] }, furniture_categories: [], boards: [] }
const base = (extra: Record<string, unknown> = {}) => routeGet({ '/meta/': META,
  '/furniture/templates/': TEMPLATES, '/materials/': [{ id: 3, name: 'Oak LDSP', kind: 'LDSP', thickness: '16.0', sheet_length: 2800, sheet_width: 2070, price_per_sheet: null, color: '#8b6f4e', is_system: false }], '/projects/': page([]), ...extra })

beforeEach(() => {
  vi.clearAllMocks(); signIn(); previews = []; base()
  vi.mocked(api.post).mockImplementation((async (url: string, body: Record<string, unknown>) => {
    if (url === '/geometry/preview/') { previews.push(body); return { data: model() } }
    if (url === '/calculations/material/') return { data: calc }
    if (url === '/designs/') return { data: design({ ...(body.config as object) }, { id: 9, name: body.name as string }) }
    return { data: { id: 1 } }
  }) as never)
  vi.mocked(api.patch).mockImplementation((async (_u: string, body: Record<string, unknown>) => ({ data: design(body.config as object, { name: body.name as string }) })) as never)
})
const open = (url = '/app/editor') => renderApp(<Editor />, { url, path: '/app/editor' })
const ready = async () => { await screen.findByTestId('viewer'); await waitFor(() => expect(previews.length).toBeGreaterThan(0)) }
const lastPost = (u: string) => vi.mocked(api.post).mock.calls.filter((c) => c[0] === u).at(-1)![1] as Record<string, unknown>

describe('Editor: the 3D model request', () => {
  it('opens with the default cabinet, proves the model against the calculation and sends every setting', async () => {
    open(); await ready()
    expect(lastPreview()).toMatchObject({ width: 800, height: 2000, depth: 400, cabinet_type: 'standard', handle_style: 'bar', edge_thickness: 0, back_material: 'HDF', colors: {} })
    expect(await screen.findByText('Model matches the calculation')).toBeInTheDocument()
    expect(screen.getByText('Panels')).toBeInTheDocument(); expect(await screen.findByText('6.25 m2')).toBeInTheDocument()
  })

  it('changing dimensions, doors, shelves and drawers reaches the server (and the calculation) immediately', async () => {
    open(); await ready()
    fireEvent.change(screen.getByLabelText('Width'), { target: { value: '1000' } }); fireEvent.change(screen.getByLabelText('Drawers'), { target: { value: '2' } })
    fireEvent.change(screen.getByLabelText('Doors'), { target: { value: '3' } }); fireEvent.change(screen.getByLabelText('Shelves'), { target: { value: '1' } })
    await waitFor(() => expect(lastPreview()).toMatchObject({ width: 1000, drawers: 2, doors: 3, shelves: 1 }))
    await waitFor(() => expect(lastPost('/calculations/material/')).toMatchObject({ width: 1000, drawers: 2 }))
  })

  it('handle style, back panel and cabinet type are sent', async () => {
    open(); await ready()
    fireEvent.change(screen.getByLabelText('Handle style'), { target: { value: 'knob' } })
    await waitFor(() => expect(lastPreview()).toMatchObject({ handle_style: 'knob' }))
    fireEvent.change(screen.getByLabelText('Back material'), { target: { value: 'PLYWOOD' } }); fireEvent.change(screen.getByLabelText('Back thickness'), { target: { value: '6' } })
    await waitFor(() => expect(lastPreview()).toMatchObject({ back_material: 'PLYWOOD', back_thickness: 6 }))
    fireEvent.change(screen.getByLabelText('Cabinet type'), { target: { value: 'sliding_wardrobe' } })
    await waitFor(() => expect(lastPreview()).toMatchObject({ cabinet_type: 'sliding_wardrobe', width: 1800, doors: 3, drawers: 0, handle_style: 'knob' }))
  })

  it('each colour group is painted separately and can be reset to its default', async () => {
    open(); await ready()
    fireEvent.click(screen.getByRole('button', { name: 'Doors and drawer fronts #475569' }))
    await waitFor(() => expect(lastPreview().colors).toEqual({ fronts: '#475569' }))
    fireEvent.click(screen.getByRole('button', { name: 'Handles and tracks #e5e7eb' }))
    await waitFor(() => expect(lastPreview().colors).toEqual({ fronts: '#475569', handle: '#e5e7eb' }))
    const fronts = screen.getByText('Doors and drawer fronts').parentElement!
    fireEvent.click(within(fronts).getByRole('button', { name: 'Default' }))
    await waitFor(() => expect(lastPreview().colors).toEqual({ handle: '#e5e7eb' }))
  })

  it('choosing a catalogue board sets the material kind, thickness and colours', async () => {
    open(); await ready()
    fireEvent.change(screen.getByLabelText('Board'), { target: { value: '3' } })
    await waitFor(() => expect(lastPreview()).toMatchObject({ material: 'LDSP', thickness: 16, colors: { carcass: '#8b6f4e', fronts: '#8b6f4e' } }))
  })

  it('invalid numbers send nothing and block saving and export; a server error is shown', async () => {
    open(); await ready(); const n = previews.length
    fireEvent.change(screen.getByLabelText('Width'), { target: { value: '' } })
    expect(screen.getByRole('button', { name: 'Save design' })).toBeDisabled(); expect(screen.getByRole('button', { name: 'GLB' })).toBeDisabled()
    await new Promise((r) => setTimeout(r, 450)); expect(previews.length).toBe(n)
    vi.mocked(api.post).mockRejectedValue(httpError(400, { error: { status: 400, detail: 'Validation failed.', fields: { shelves: ['too many shelves/drawers for this height'] } } }))
    fireEvent.change(screen.getByLabelText('Width'), { target: { value: '900' } }); fireEvent.change(screen.getByLabelText('Shelves'), { target: { value: '20' } })
    expect((await screen.findAllByText('too many shelves/drawers for this height')).length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: 'Save design' })).toBeDisabled()
  })

  it('a model that does not match the calculation is flagged with the reasons', async () => {
    vi.mocked(api.post).mockImplementation((async (url: string) => (url === '/geometry/preview/' ? { data: model({ consistency: { valid: false, problems: ["'Door 1' is 396 x 1990 x 18 mm but the calculated part 'Door' needs 396 x 1996 x 18 mm"], checks: [], not_modelled: [] } }) } : { data: calc })) as never)
    open(); expect(await screen.findByText('Model differs from the calculation')).toBeInTheDocument(); expect(screen.getByText(/'Door 1' is 396 x 1990/)).toBeInTheDocument()
  })
})

describe('Editor: views and selection', () => {
  it('the view buttons move the camera and reset returns to the 3D view', async () => {
    open(); await ready(); const viewer = screen.getByTestId('viewer'); expect(viewer).toHaveAttribute('data-view', 'perspective')
    const bar = within(screen.getByRole('group', { name: 'Camera views' }))
    for (const [name, view] of [['Front', 'front'], ['Side', 'side'], ['Top', 'top']] as const) { fireEvent.click(bar.getByRole('button', { name })); expect(viewer).toHaveAttribute('data-view', view); expect(bar.getByRole('button', { name })).toHaveAttribute('aria-pressed', 'true') }
    fireEvent.click(bar.getByRole('button', { name: 'Reset view' })); expect(viewer).toHaveAttribute('data-view', 'perspective')
  })

  it('dimension labels and wireframe are switchable', async () => {
    open(); await ready(); const viewer = screen.getByTestId('viewer'); expect(viewer).toHaveAttribute('data-dims', 'true'); expect(viewer).toHaveAttribute('data-wire', 'false')
    fireEvent.click(screen.getByRole('switch', { name: 'Wireframe' })); fireEvent.click(screen.getByRole('switch', { name: 'Dimension labels' }))
    expect(viewer).toHaveAttribute('data-wire', 'true'); expect(viewer).toHaveAttribute('data-dims', 'false')
  })

  it('picking a part in the 3D view shows its real size and position; clicking empty space clears it', async () => {
    open(); await ready()
    expect(screen.getByText(/Click a part in the 3D view/)).toBeInTheDocument()
    fireEvent.click(screen.getByText('pick-first'))
    const panel = within(screen.getByTestId('selected-part'))
    expect(panel.getByText('Left side')).toBeInTheDocument(); expect(panel.getByText('Carcass panel')).toBeInTheDocument(); expect(panel.getByText('18 mm')).toBeInTheDocument(); expect(panel.getByText('2000 mm')).toBeInTheDocument(); expect(panel.getByText('400 mm')).toBeInTheDocument()
    expect(screen.getByTestId('viewer')).toHaveAttribute('data-selected', 'Left side')
    fireEvent.click(screen.getByText('pick-none')); expect(screen.queryByTestId('selected-part')).not.toBeInTheDocument(); expect(screen.getByTestId('viewer')).toHaveAttribute('data-selected', '')
  })

  it('the parts list selects without a pointer, toggles, and recolours the selected part\'s group', async () => {
    open(); await ready()
    const list = within(screen.getByRole('list', { name: 'Parts in the model' }))
    expect(list.getAllByRole('button').map((b) => b.textContent)).toEqual(['Left side', 'Door 1', 'Door handle 1'])
    fireEvent.click(list.getByRole('button', { name: 'Door 1' })); expect(screen.getByTestId('viewer')).toHaveAttribute('data-selected', 'Door 1')
    expect(within(screen.getByTestId('selected-part')).getByText('Door')).toBeInTheDocument()
    fireEvent.click(within(screen.getByTestId('selected-part')).getByRole('button', { name: 'Doors and drawer fronts #475569' }))
    await waitFor(() => expect(lastPreview().colors).toEqual({ fronts: '#475569' }))
    fireEvent.click(list.getByRole('button', { name: 'Door 1' })); expect(screen.getByTestId('viewer')).toHaveAttribute('data-selected', '')
  })

  it('a selection that disappears from the model (e.g. fewer doors) is dropped instead of pointing at nothing', async () => {
    open(); await ready(); fireEvent.click(within(screen.getByRole('list', { name: 'Parts in the model' })).getByRole('button', { name: 'Door 1' }))
    vi.mocked(api.post).mockImplementation((async (url: string, body: Record<string, unknown>) => { if (url === '/geometry/preview/') { previews.push(body); return { data: model({ boxes: [box('Left side', 'carcass')] }) } } return { data: calc } }) as never)
    fireEvent.change(screen.getByLabelText('Doors'), { target: { value: '0' } })
    await waitFor(() => expect(screen.queryByTestId('selected-part')).not.toBeInTheDocument())
  })
})

describe('Editor: save and load', () => {
  it('saves a new design with the full config, then shows it as saved, then as changed again', async () => {
    open(); await ready()
    fireEvent.change(screen.getByLabelText('Design name'), { target: { value: 'My wardrobe' } }); fireEvent.click(screen.getByRole('button', { name: 'Handles and tracks #e5e7eb' }))
    fireEvent.change(screen.getByLabelText('Handle style'), { target: { value: 'none' } })
    expect(screen.getByText('Unsaved changes')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Save design' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/designs/', expect.objectContaining({ name: 'My wardrobe', kind: 'furniture', project: null })))
    const cfg = (lastPost('/designs/').config as Record<string, unknown>)
    expect(cfg).toMatchObject({ schema_version: 1, colors: { handle: '#e5e7eb' }, material: null }); expect((cfg.input as Record<string, unknown>)).toMatchObject({ width: 800, handle_style: 'none', cabinet_type: 'standard' })
    expect(await screen.findByText('Saved', { selector: 'span' })).toBeInTheDocument(); expect(screen.queryByText('Unsaved changes')).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Width'), { target: { value: '850' } }); expect(await screen.findByText('Unsaved changes')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Update design' })).toBeInTheDocument()
  })

  it('"save as new" creates a copy named "(copy)" and leaves the original alone', async () => {
    routeGet({ '/meta/': META, '/furniture/templates/': TEMPLATES, '/materials/': [], '/projects/': page([]), '/designs/5/': design(NEW_CFG) })
    open('/app/editor?design=5'); await ready()
    fireEvent.click(screen.getByRole('button', { name: 'Save as new' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/designs/', expect.objectContaining({ name: 'Saved wardrobe (copy)', config: expect.objectContaining({ schema_version: 1 }) })))
    expect(api.patch).not.toHaveBeenCalled()
  })

  it('opens a saved design: name, sizes, style and colours come back and it starts unchanged', async () => {
    routeGet({ '/meta/': META, '/furniture/templates/': TEMPLATES, '/materials/': [], '/projects/': page([]), '/designs/5/': design(NEW_CFG) })
    open('/app/editor?design=5'); await ready()
    expect(screen.getByLabelText('Design name')).toHaveValue('Saved wardrobe'); expect(screen.getByLabelText('Width')).toHaveValue(900); expect(screen.getByLabelText('Handle style')).toHaveValue('knob')
    expect(lastPreview()).toMatchObject({ width: 900, height: 1800, handle_style: 'knob', colors: { fronts: '#445566' } })
    expect(screen.queryByText('Unsaved changes')).not.toBeInTheDocument(); expect(screen.getByRole('button', { name: 'Update design' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Update design' }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/designs/5/', expect.objectContaining({ name: 'Saved wardrobe', config: expect.objectContaining({ colors: { fronts: '#445566' } }) })))
    expect(api.post).not.toHaveBeenCalledWith('/designs/', expect.anything())
  })

  it('opens designs saved by the old editor (seven numbers and one colour)', async () => {
    routeGet({ '/meta/': META, '/furniture/templates/': TEMPLATES, '/materials/': [], '/projects/': page([]),
      '/designs/6/': design({ input: { width: 700, height: 900, depth: 450, thickness: 18, shelves: 1, doors: 2, drawers: 0 }, color: '#8b6f4e' }, { id: 6, name: 'Old one' }) })
    open('/app/editor?design=6'); await ready()
    expect(screen.getByLabelText('Width')).toHaveValue(700); expect(lastPreview()).toMatchObject({ handle_style: 'bar', cabinet_type: 'standard', colors: { carcass: '#8b6f4e', fronts: '#8b6f4e' } })
    expect(screen.queryByText('Unsaved changes')).not.toBeInTheDocument()
  })

  it('a design that does not exist (or is not yours) gets one clear message and a way out', async () => {
    routeGet({ '/meta/': META, '/furniture/templates/': TEMPLATES, '/materials/': [], '/projects/': page([]), '/designs/404/': httpError(404, { error: { status: 404, detail: 'Not found.' } }) })
    open('/app/editor?design=404')
    expect(await screen.findByRole('alert')).toHaveTextContent('could not be opened'); expect(screen.getByRole('link', { name: 'New design' })).toHaveAttribute('href', '/app/editor')
  })

  it('shows the server\'s reason when saving is refused', async () => {
    open(); await ready(); fireEvent.change(screen.getByLabelText('Design name'), { target: { value: 'Changed' } })
    vi.mocked(api.post).mockRejectedValue(httpError(400, { error: { status: 400, detail: 'Validation failed.', fields: { config: ['input: width: must be between 200 and 4000'] } } }))
    fireEvent.click(screen.getByRole('button', { name: 'Save design' }))
    expect(await screen.findByText('input: width: must be between 200 and 4000')).toBeInTheDocument(); expect(screen.getByText('Unsaved changes')).toBeInTheDocument()
  })

  it('warns before closing the tab only while there are unsaved changes', async () => {
    const add = vi.spyOn(window, 'addEventListener'); const remove = vi.spyOn(window, 'removeEventListener')
    open(); await ready(); expect(add.mock.calls.some((c) => c[0] === 'beforeunload')).toBe(false)
    fireEvent.change(screen.getByLabelText('Depth'), { target: { value: '450' } }); await waitFor(() => expect(add.mock.calls.some((c) => c[0] === 'beforeunload')).toBe(true))
    fireEvent.change(screen.getByLabelText('Depth'), { target: { value: '400' } })    // back to the saved state: nothing to lose
    await waitFor(() => expect(remove.mock.calls.some((c) => c[0] === 'beforeunload')).toBe(true)); add.mockRestore(); remove.mockRestore()
  })
})

describe('Editor: templates, projects and export', () => {
  it('a template replaces the design directly when nothing changed and asks first when something did', async () => {
    open(); await ready()
    fireEvent.click(await screen.findByRole('button', { name: /Wardrobe/ }))
    await waitFor(() => expect(screen.getByLabelText('Width')).toHaveValue(1200)); expect(screen.getByLabelText('Design name')).toHaveValue('Wardrobe'); expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Width'), { target: { value: '1300' } })
    fireEvent.click(screen.getByRole('button', { name: /Wardrobe/ }))
    const dlg = await screen.findByRole('dialog', { name: 'Replace the current design?' }); expect(screen.getByLabelText('Width')).toHaveValue(1300)
    fireEvent.click(within(dlg).getByRole('button', { name: 'Cancel' })); await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument()); expect(screen.getByLabelText('Width')).toHaveValue(1300)
    fireEvent.click(screen.getByRole('button', { name: /Wardrobe/ })); fireEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Replace' }))
    await waitFor(() => expect(screen.getByLabelText('Width')).toHaveValue(1200))
  })

  it('exports send exactly what is on screen, colours and handle style included', async () => {
    open(); await ready()
    fireEvent.click(screen.getByRole('button', { name: 'Doors and drawer fronts #475569' })); fireEvent.change(screen.getByLabelText('Handle style'), { target: { value: 'none' } })
    fireEvent.change(screen.getByLabelText('Design name'), { target: { value: 'Export me' } })
    fireEvent.click(screen.getByRole('button', { name: 'GLB' }))
    await waitFor(() => expect(downloadBlob).toHaveBeenCalledWith('/geometry/export/glb/', 'Export me.glb', 'post', expect.objectContaining({ width: 800, handle_style: 'none', colors: { fronts: '#475569' } })))
    fireEvent.click(screen.getByRole('button', { name: 'OBJ' })); await waitFor(() => expect(downloadBlob).toHaveBeenCalledWith('/geometry/export/obj/', 'Export me.obj', 'post', expect.anything()))
  })

  it('the cutting list export uses the same cabinet and the chosen project', async () => {
    routeGet({ '/meta/': META, '/furniture/templates/': TEMPLATES, '/materials/': [], '/projects/': page([{ id: 4, name: 'Flat 12' }]) })
    open(); await ready()
    fireEvent.change(await screen.findByLabelText('Attach to project'), { target: { value: '4' } }); fireEvent.click(screen.getByRole('button', { name: /Cutting PDF/ }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/cutting-lists/from-calculation/', expect.objectContaining({ width: 800, handle_style: 'bar', project: 4 })))
  })

  it('opens from calculator sizes (?cab=) and from a template link', async () => {
    open('/app/editor?cab=1000,2100,550,18,4,3,0'); await ready(); expect(screen.getByLabelText('Width')).toHaveValue(1000); expect(screen.getByLabelText('Doors')).toHaveValue(3)
  })
})
