import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { api } from '../../lib/api'
import type { Question, RoomConfig, RoomFlow, RoomItem, RoomStep } from '../../lib/room'
import { httpError, page, renderApp, routeGet, signIn } from '../../test/utils'
import Rooms from './Rooms'

vi.mock('../../lib/api', async (orig) => ({ ...(await orig<typeof import('../../lib/api')>()), api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }))
vi.mock('../../components/three/LazyViewer', () => ({ CabinetViewer: ({ boxes }: { boxes: unknown[] }) => <div data-testid="viewer">{boxes.length} boxes</div> }))
beforeEach(() => { vi.clearAllMocks(); signIn({ role: 'homeowner' }) })

const loc = (en: string) => ({ en, uz: en + ' (uz)', ru: en + ' (ru)' })
const item = (o: Partial<RoomItem> = {}): RoomItem => ({ id: 'it1', template: 'bedside', name: 'Bedside table', x: 100, z: 200, rot: 0, width: 450, depth: 400, height: 500, shelves: 0, doors: 0, drawers: 2, color: '#e5e7eb', ...o })
const config = (items: RoomItem[] = [item()]): RoomConfig => ({ schema: 'room.v1', goal: 'bedroom', style: 'modern', room: { width: 4000, length: 3000, height: 2700 }, openings: [{ type: 'door', wall: 'north', offset: 1000, width: 900, height: 2100, sill: 0 }], items, not_placed: [], colors: { wall: '#cbd5e1', floor: '#d6c9b4', item: '#e5e7eb' } })
const q = (step: RoomStep, o: Partial<Question> = {}): Question => ({ step, title: loc('Title ' + step), prompt: loc('Prompt ' + step), index: 1, total: 7, can_back: false, optional: false, kind: 'choice', ...o })
const flow = (o: Partial<RoomFlow> = {}): RoomFlow => ({ id: 5, status: 'active', step: 'goal', answers: {}, question: q('goal', { options: [{ id: 'kitchen', label: loc('Kitchen') }, { id: 'bedroom', label: loc('Bedroom') }] }), design: null, room: null, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', ...o })
const furnish = (items: RoomItem[] = [item()], o: Partial<RoomFlow> = {}): RoomFlow => flow({ step: 'furnish', design: 9, room: { config: config(items), warnings: [] },
  question: q('furnish', { kind: 'furnish', index: 7, can_back: true, max_items: 60, catalog: [{ slug: 'bedside', category: 'bedroom', label: loc('Bedside table'), name: 'Bedside table', defaults: { width: 450, height: 500, depth: 400 } }, { slug: 'dresser', category: 'bedroom', label: loc('Dresser'), name: 'Dresser', defaults: { width: 900, height: 1000, depth: 480 } }] }), ...o })
const open = (f: RoomFlow) => { routeGet({ '/rooms/5/': f }); return renderApp(<Rooms />, { url: '/app/rooms/5', path: '/app/rooms/:id' }) }

describe('Room designer: list', () => {
  it('lists my room designs with their state and starts a new one', async () => {
    routeGet({ '/rooms/': page([{ id: 5, status: 'active', step: 'size', goal: 'bedroom', design: null, created_at: '2026-01-01T00:00:00Z', updated_at: new Date().toISOString() }, { id: 6, status: 'completed', step: 'done', goal: null, design: 3, created_at: '2026-01-01T00:00:00Z', updated_at: new Date().toISOString() }]) })
    vi.mocked(api.post).mockResolvedValue({ data: flow({ id: 12 }) } as never)
    renderApp(<Rooms />, { url: '/app/rooms', path: '/app/rooms' })
    expect(await screen.findByText('Bedroom')).toBeInTheDocument(); expect(screen.getByText('In progress')).toBeInTheDocument(); expect(screen.getByText('Saved')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Continue' })).toBeInTheDocument(); expect(screen.getByRole('button', { name: 'Open' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /New room design/ }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/rooms/'))
  })
  it('shows an empty state and asks before deleting', async () => {
    routeGet({ '/rooms/': page([]) })
    renderApp(<Rooms />, { url: '/app/rooms', path: '/app/rooms' })
    expect(await screen.findByText('No room designs yet')).toBeInTheDocument()
  })
  it('deletes after confirmation', async () => {
    routeGet({ '/rooms/': page([{ id: 5, status: 'active', step: 'goal', goal: null, design: null, created_at: '2026-01-01T00:00:00Z', updated_at: new Date().toISOString() }]) })
    vi.mocked(api.delete).mockResolvedValue({} as never)
    renderApp(<Rooms />, { url: '/app/rooms', path: '/app/rooms' })
    fireEvent.click(await screen.findByRole('button', { name: 'Delete #5' }))
    const dlg = within(await screen.findByRole('dialog')); expect(api.delete).not.toHaveBeenCalled()
    fireEvent.click(dlg.getByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(api.delete).toHaveBeenCalledWith('/rooms/5/'))
  })
})

describe('Room designer: wizard', () => {
  it('renders the server question and sends the chosen answer for the current step', async () => {
    open(flow()); vi.mocked(api.post).mockResolvedValue({ data: flow({ step: 'photo', question: q('photo', { kind: 'photo', optional: true, index: 2, can_back: true }) }) } as never)
    expect(await screen.findByText('Title goal')).toBeInTheDocument(); expect(screen.getByText('Step 1 of 7')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('radio', { name: 'Bedroom' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/rooms/5/answer/', { step: 'goal', value: 'bedroom' }))
    expect(await screen.findByText('Title photo')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Skip' }))
    await waitFor(() => expect(api.post).toHaveBeenLastCalledWith('/rooms/5/answer/', { step: 'photo', value: { skip: true } }))
  })
  it('shows the server refusal next to the field and keeps the form', async () => {
    const size = flow({ step: 'size', question: q('size', { kind: 'number_group', unit: 'mm', index: 4, can_back: true, fields: [{ key: 'width', type: 'number', label: loc('Width (mm)'), min: 1000, max: 15000 }, { key: 'length', type: 'number', label: loc('Length (mm)'), min: 1000, max: 15000 }, { key: 'height', type: 'number', label: loc('Height (mm)'), min: 2000, max: 4500 }] }) })
    open(size); vi.mocked(api.post).mockRejectedValue(httpError(400, { error: { status: 400, detail: 'Validation failed.', fields: { width: ['must be between 1000 and 15000'] } } }))
    fireEvent.change(await screen.findByLabelText('Width (mm)'), { target: { value: '100' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('must be between 1000 and 15000')).toBeInTheDocument()
    expect(api.post).toHaveBeenCalledWith('/rooms/5/answer/', { step: 'size', value: expect.objectContaining({ width: 100 }) })
    expect(screen.getByLabelText('Width (mm)')).toHaveValue(100)
  })
  it('lets the user pick furniture for the room', async () => {
    const el = flow({ step: 'elements', question: q('elements', { kind: 'number_group', index: 3, can_back: true, fields: [{ key: 'doors', type: 'number', label: loc('Doors'), min: 0, max: 2, default: 1 }, { key: 'windows', type: 'number', label: loc('Windows'), min: 0, max: 4, default: 1 }, { key: 'furniture', type: 'multi', label: loc('Furniture'), options: [{ id: 'bedside', label: loc('Bedside table') }, { id: 'dresser', label: loc('Dresser') }] }] }) })
    open(el); vi.mocked(api.post).mockResolvedValue({ data: el } as never)
    fireEvent.click(await screen.findByRole('checkbox', { name: 'Dresser' }))
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/rooms/5/answer/', { step: 'elements', value: { doors: 1, windows: 1, furniture: ['dresser'] } }))
  })
  it('asks for every promised door and window and sends them together', async () => {
    const ops = flow({ step: 'openings', question: q('openings', { kind: 'openings', index: 5, can_back: true, required: { doors: 1, windows: 1 }, room: { width: 4000, length: 3000, height: 2700 }, walls: [{ id: 'north', label: loc('North wall') }, { id: 'east', label: loc('East wall') }, { id: 'south', label: loc('South wall') }, { id: 'west', label: loc('West wall') }], wall_lengths: { north: 4000, east: 3000, south: 4000, west: 3000 }, limits: { door: { width: [600, 1200], height: [1800, 2400] }, window: { width: [300, 3000], height: [300, 2400], sill: [0, 1500] }, edge_margin: 100, gap: 100 } }) })
    open(ops); vi.mocked(api.post).mockResolvedValue({ data: ops } as never)
    expect(await screen.findByText('Door 1')).toBeInTheDocument(); expect(screen.getByText('Window 1')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    await waitFor(() => expect(api.post).toHaveBeenCalled())
    const sent = vi.mocked(api.post).mock.calls[0][1] as { step: string; value: { type: string }[] }
    expect(sent.step).toBe('openings'); expect(sent.value.map((o) => o.type)).toEqual(['door', 'window'])
  })
  const shortRoom = (required: { doors: number; windows: number }) => {
    const walls = [{ id: 'north', label: loc('North wall') }, { id: 'east', label: loc('East wall') }, { id: 'south', label: loc('South wall') }, { id: 'west', label: loc('West wall') }] as never
    return flow({ step: 'openings', question: q('openings', { kind: 'openings', index: 5, can_back: true, required, room: { width: 4000, length: 1000, height: 2700 }, walls, wall_lengths: { north: 4000, east: 1000, south: 4000, west: 1000 }, limits: { door: { width: [600, 1200], height: [1800, 2400] }, window: { width: [300, 3000], height: [300, 2400], sill: [0, 1500] }, edge_margin: 100, gap: 100 } }) })
  }
  it('puts every default opening on a wall where it fits and never on top of another one (2 doors + 4 windows in a 4 x 1 m room)', async () => {
    const ops = shortRoom({ doors: 2, windows: 4 }); open(ops); vi.mocked(api.post).mockResolvedValue({ data: ops } as never)
    expect(await screen.findByText('Window 4')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    await waitFor(() => expect(api.post).toHaveBeenCalled())
    const sent = (vi.mocked(api.post).mock.calls[0][1] as { value: { wall: string; offset: number; width: number }[] }).value
    expect(sent).toHaveLength(6)
    const len: Record<string, number> = { north: 4000, east: 1000, south: 4000, west: 1000 }
    for (const w of Object.keys(len)) {
      const on = sent.filter((o) => o.wall === w).sort((a, b) => a.offset - b.offset)
      on.forEach((o, i) => { expect(o.offset).toBeGreaterThanOrEqual(100); expect(o.offset + o.width).toBeLessThanOrEqual(len[w] - 100); if (i) expect(o.offset - (on[i - 1].offset + on[i - 1].width)).toBeGreaterThanOrEqual(100) })
    }
  })
  it('explains per opening (in the user language) when a window is moved to a wall it does not fit, and blocks Next without calling the server', async () => {
    const ops = shortRoom({ doors: 0, windows: 1 }); open(ops); vi.mocked(api.post).mockResolvedValue({ data: ops } as never)
    expect(await screen.findByText('Window 1')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Wall'), { target: { value: 'east' } })
    expect(await screen.findByRole('alert')).toHaveTextContent(/does not fit the 1000 mm wall/)
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(api.post).not.toHaveBeenCalled()
  })
  it('flags two openings that overlap on one wall', async () => {
    const ops = shortRoom({ doors: 0, windows: 2 }); open(ops)
    expect(await screen.findByText('Window 2')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    const walls = screen.getAllByLabelText('Wall'); fireEvent.change(walls[1], { target: { value: (walls[0] as HTMLSelectElement).value } })
    const offsets = screen.getAllByLabelText(/^Distance|offset/i)
    fireEvent.change(offsets[1], { target: { value: String((offsets[0] as HTMLInputElement).value) } })
    expect(await screen.findByRole('alert')).toHaveTextContent(/overlaps another one/)
  })
  it('goes back one step and reports a conflict', async () => {
    open(flow({ step: 'size', question: q('size', { kind: 'number_group', can_back: true, index: 4, fields: [] }) }))
    vi.mocked(api.post).mockResolvedValue({ data: flow() } as never)
    fireEvent.click(await screen.findByRole('button', { name: 'Back' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/rooms/5/back/'))
    expect(await screen.findByText('Title goal')).toBeInTheDocument()
  })
  it('says so when the design does not exist or is not mine', async () => {
    routeGet({ '/rooms/5/': httpError(404, { error: { status: 404, detail: 'Not found.' } }) })
    renderApp(<Rooms />, { url: '/app/rooms/5', path: '/app/rooms/:id' })
    expect(await screen.findByText('This room design was not found.')).toBeInTheDocument()
  })
})

describe('Room designer: furnishing', () => {
  it('shows the plan with every piece and the warnings from the server', async () => {
    open(furnish([item(), item({ id: 'it2', name: 'Dresser', template: 'dresser', x: 2000 })], { room: { config: config([item(), item({ id: 'it2', name: 'Dresser', template: 'dresser', x: 2000 })]), warnings: [{ code: 'door_zone', item: 'it2', message: 'blocks the 800 mm area in front of a door' }] } }))
    const plan = await screen.findByRole('group', { name: 'Top-down room plan' })
    expect(within(plan).getAllByRole('button')).toHaveLength(2)
    expect(within(screen.getByRole('list', { name: 'Warnings' })).getByText(/Dresser: blocks the 800 mm area/)).toBeInTheDocument()
  })
  it('adds a piece of furniture and selects it', async () => {
    const f = furnish(); const after = furnish([item(), item({ id: 'new', name: 'Dresser', template: 'dresser', x: 1000 })], { item: item({ id: 'new', name: 'Dresser' }) })
    open(f); vi.mocked(api.post).mockResolvedValue({ data: after } as never)
    fireEvent.change(await screen.findByLabelText('Furniture'), { target: { value: 'dresser' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add to room' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/rooms/5/items/', { template: 'dresser' }))
    expect(await within(await screen.findByTestId('item-panel')).findByText('Dresser')).toBeInTheDocument()
  })
  it('moves the selected piece with the arrow keys and sends the new position', async () => {
    open(furnish()); vi.mocked(api.patch).mockResolvedValue({ data: furnish([item({ x: 110 })]) } as never)
    const piece = await screen.findByRole('button', { name: /Bedside table, 450 x 400 mm/ })
    fireEvent.keyDown(piece, { key: 'ArrowRight' })
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/rooms/5/items/it1/', { x: 110, z: 200 }))
    fireEvent.keyDown(piece, { key: 'ArrowDown', shiftKey: true })
    await waitFor(() => expect(api.patch).toHaveBeenLastCalledWith('/rooms/5/items/it1/', { x: 110, z: 300 }))
  })
  it('drags a piece with the pointer, clamps it to the room, and sends the dropped position once', async () => {
    open(furnish()); vi.mocked(api.patch).mockResolvedValue({ data: furnish([item({ x: 1100, z: 900 })]) } as never)
    const plan = await screen.findByRole('group', { name: 'Top-down room plan' })
    vi.spyOn(plan, 'getBoundingClientRect').mockReturnValue({ left: 0, top: 0, width: 4800, height: 3800, right: 4800, bottom: 3800, x: 0, y: 0, toJSON: () => ({}) })   // 1 px = 1 mm in this test
    const piece = screen.getByRole('button', { name: /Bedside table/ })
    fireEvent.pointerDown(piece, { clientX: 700, clientY: 800, pointerId: 1 })               // grabs the piece at (300, 400) mm, 200 mm inside its corner
    fireEvent.pointerMove(piece, { clientX: 1200, clientY: 1000, pointerId: 1 })
    fireEvent.pointerMove(piece, { clientX: 1700, clientY: 1500, pointerId: 1 })
    expect(api.patch).not.toHaveBeenCalled()                                                  // nothing is sent while dragging
    fireEvent.pointerUp(piece, { clientX: 1700, clientY: 1500, pointerId: 1 })
    await waitFor(() => expect(api.patch).toHaveBeenCalledTimes(1)); expect(api.patch).toHaveBeenCalledWith('/rooms/5/items/it1/', { x: 1100, z: 900 })
  })
  it('does not send anything when a piece is dropped where it started or dragged outside, it is clamped', async () => {
    open(furnish()); const plan = await screen.findByRole('group', { name: 'Top-down room plan' })
    vi.spyOn(plan, 'getBoundingClientRect').mockReturnValue({ left: 0, top: 0, width: 4800, height: 3800, right: 4800, bottom: 3800, x: 0, y: 0, toJSON: () => ({}) })
    const piece = screen.getByRole('button', { name: /Bedside table/ })
    fireEvent.pointerDown(piece, { clientX: 600, clientY: 700, pointerId: 1 }); fireEvent.pointerUp(piece, { clientX: 600, clientY: 700, pointerId: 1 })
    expect(api.patch).not.toHaveBeenCalled()
    vi.mocked(api.patch).mockResolvedValue({ data: furnish() } as never)
    fireEvent.pointerDown(piece, { clientX: 600, clientY: 700, pointerId: 1 }); fireEvent.pointerMove(piece, { clientX: 99999, clientY: 99999, pointerId: 1 }); fireEvent.pointerUp(piece, { pointerId: 1 })
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/rooms/5/items/it1/', { x: 4000 - 450, z: 3000 - 400 }))
  })
  it('does not send a move that would leave the room', async () => {
    open(furnish([item({ x: 0, z: 0 })])); const piece = await screen.findByRole('button', { name: /Bedside table/ })
    fireEvent.keyDown(piece, { key: 'ArrowLeft' }); fireEvent.keyDown(piece, { key: 'ArrowUp' })
    expect(api.patch).not.toHaveBeenCalled()
  })
  it('applies typed sizes, shows the server message when refused, and rotates', async () => {
    open(furnish()); vi.mocked(api.patch).mockRejectedValueOnce(httpError(400, { error: { status: 400, detail: 'Validation failed.', fields: { position: ['overlaps another item (Dresser)'] } } }))
    fireEvent.keyDown(await screen.findByRole('button', { name: /Bedside table/ }), { key: 'Enter' })
    const panel = within(await screen.findByTestId('item-panel'))
    fireEvent.change(panel.getByLabelText('Width'), { target: { value: '600' } })
    fireEvent.click(panel.getByRole('button', { name: 'Apply' }))
    expect(await panel.findByText('overlaps another item (Dresser)')).toBeInTheDocument()
    expect(api.patch).toHaveBeenCalledWith('/rooms/5/items/it1/', { x: 100, z: 200, width: 600, depth: 400, height: 500 })
    vi.mocked(api.patch).mockResolvedValueOnce({ data: furnish([item({ rot: 90 })]) } as never)
    fireEvent.click(panel.getByRole('button', { name: /Rotate 90°/ }))
    await waitFor(() => expect(api.patch).toHaveBeenLastCalledWith('/rooms/5/items/it1/', { rot: 90 }))
  })
  it('removes a piece', async () => {
    open(furnish()); vi.mocked(api.delete).mockResolvedValue({ data: furnish([]) } as never)
    fireEvent.keyDown(await screen.findByRole('button', { name: /Bedside table/ }), { key: 'Enter' })
    fireEvent.click(await screen.findByRole('button', { name: 'Remove' }))
    await waitFor(() => expect(api.delete).toHaveBeenCalledWith('/rooms/5/items/it1/'))
  })
  it('re-arranges only after confirmation, and finishes', async () => {
    open(furnish()); vi.mocked(api.post).mockResolvedValue({ data: furnish() } as never)
    fireEvent.click(await screen.findByRole('button', { name: 'Arrange automatically' }))
    const dlg = within(await screen.findByRole('dialog')); expect(api.post).not.toHaveBeenCalled()
    fireEvent.click(dlg.getByRole('button', { name: 'Arrange automatically' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/rooms/5/reset-layout/'))
    fireEvent.click(screen.getByRole('button', { name: 'Finish and save' }))
    await waitFor(() => expect(api.post).toHaveBeenLastCalledWith('/rooms/5/finish/'))
  })
  it('loads the 3D model only when the 3D tab is opened', async () => {
    routeGet({ '/rooms/5/': furnish(), '/rooms/5/model/': { dimensions: { width: 4000, depth: 3000, length: 3000, height: 2700, wall_thickness: 100 }, boxes: [{ name: 'Floor', kind: 'floor', x: 0, y: 0, z: 0, sx: 1, sy: 1, sz: 1, color: '#fff' }], warnings: [] } })
    renderApp(<Rooms />, { url: '/app/rooms/5', path: '/app/rooms/:id' })
    await screen.findByRole('group', { name: 'Top-down room plan' })
    expect(vi.mocked(api.get).mock.calls.some((c) => c[0] === '/rooms/5/model/')).toBe(false)
    fireEvent.click(screen.getByRole('tab', { name: '3D view' }))
    expect(await screen.findByTestId('viewer')).toHaveTextContent('1 boxes')
  })
  it('is read-only once the design is finished', async () => {
    open(furnish([item()], { status: 'completed', step: 'done' }))
    expect(await screen.findByText(/saved and finished/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Finish and save' })).not.toBeInTheDocument(); expect(screen.queryByRole('button', { name: 'Add to room' })).not.toBeInTheDocument()
    fireEvent.keyDown(screen.getByRole('button', { name: /Bedside table/ }), { key: 'ArrowRight' })
    expect(api.patch).not.toHaveBeenCalled()
  })
})
