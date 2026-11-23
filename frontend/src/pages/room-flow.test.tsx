import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { AxiosError, type AxiosResponse } from 'axios'
import { MemoryRouter } from 'react-router-dom'
import { api } from '../lib/api'
import { translate } from '../lib/i18n'
import type { Descriptor, FlowView, RoomItem } from '../lib/roomFlow'
import RoomFlowPage from './app/RoomFlow'

const L3 = (en: string, uz = en, ru = en) => ({ en, uz, ru })
const t = (k: string) => translate('en', k)

function desc(step: string, kind: Descriptor['kind'], index: number, extra: Partial<Descriptor> = {}): Descriptor {
  return { step, kind, title: L3(`${step} title`), prompt: L3(`${step} prompt`), index, total: 7, can_back: step !== 'goal', optional: false, value: null, ...extra }
}
function view(step: string, kind: Descriptor['kind'], index: number, extra: Partial<Descriptor> = {}, over: Partial<FlowView> = {}): FlowView {
  return { id: 9, status: 'active', step, descriptor: desc(step, kind, index, extra), answers: {}, design_id: null, photo_id: null, rev: null, warnings: [], created_at: 'x', updated_at: 'x', ...over }
}
const GOAL = view('goal', 'choice', 1, { can_back: false, options: [{ id: 'kitchen', label: L3('Kitchen', 'Oshxona') }, { id: 'bedroom', label: L3('Bedroom') }] })
const PHOTO = view('photo', 'photo', 2, { optional: true })
const ELEMENTS = view('elements', 'number_group', 3, { fields: [
  { key: 'doors', type: 'number', label: L3('Doors'), min: 0, max: 2, default: 1 }, { key: 'windows', type: 'number', label: L3('Windows'), min: 0, max: 4, default: 1 },
  { key: 'furniture', type: 'multi', label: L3('Furniture'), options: [{ id: 'bedside', label: L3('Bedside table') }, { id: 'dresser', label: L3('Dresser') }] }] })
const SIZE = view('size', 'number_group', 4, { unit: 'mm', fields: [
  { key: 'width', type: 'number', label: L3('Width (mm)'), min: 1000, max: 15000 }, { key: 'length', type: 'number', label: L3('Length (mm)'), min: 1000, max: 15000 },
  { key: 'height', type: 'number', label: L3('Room height (mm)'), min: 2000, max: 4500 }] })
const WALLS = (['north', 'east', 'south', 'west'] as const).map((w) => ({ id: w, label: L3(`${w[0].toUpperCase()}${w.slice(1)} wall`) }))
const OPENINGS = view('openings', 'openings', 5, { required: { doors: 1, windows: 1 }, room: { width: 4000, length: 3000, height: 2700 }, walls: WALLS, wall_lengths: { north: 4000, east: 3000, south: 4000, west: 3000 } })

const ITEM: RoomItem = { id: 'a1b2c3d4e5f6', template: 'bedside', name: 'Bedside table', x: 100, z: 0, rot: 0, width: 450, depth: 400, height: 500, shelves: 0, doors: 0, drawers: 2, color: '#e5e7eb' }
const ITEM2: RoomItem = { ...ITEM, id: '0f0f0f0f0f0f', name: 'Dresser', template: 'dresser', x: 1000, z: 1000, width: 900, depth: 480, height: 1000 }
function furnish(items = [ITEM], rev = 3, over: Partial<FlowView> = {}): FlowView {
  return view('furnish', 'furnish', 7, { catalog: [{ slug: 'bedside', category: 'bedroom', label: L3('Bedside table'), name: 'Bedside table', defaults: {} }, { slug: 'dresser', category: 'bedroom', label: L3('Dresser'), name: 'Dresser', defaults: {} }] },
    { rev, items, room: { width: 4000, length: 3000, height: 2700 }, openings: [], design_id: 5, ...over })
}

function fail(status: number, fields: Record<string, unknown>): AxiosError {
  return new AxiosError('failed', 'ERR_BAD_REQUEST', undefined, undefined, { status, data: { error: { status, detail: status === 400 ? 'Validation failed.' : 'Request failed.', fields } } } as AxiosResponse)
}

let current: FlowView | null
const list = () => ({ data: { count: current ? 1 : 0, next: null, previous: null, results: current ? [{ id: current.id, status: current.status, step: current.step, design: null, photo: null, created_at: 'x', updated_at: 'x' }] : [] } })

function server(initial: FlowView | null) {
  current = initial
  const get = vi.spyOn(api, 'get').mockImplementation(async (url: string) => (url === '/room-flows/' ? list() : { data: current }) as never)
  const post = vi.spyOn(api, 'post').mockImplementation((async () => { throw new Error('unmocked post') }) as never)
  const patch = vi.spyOn(api, 'patch').mockImplementation((async () => { throw new Error('unmocked patch') }) as never)
  const del = vi.spyOn(api, 'delete').mockImplementation((async () => { throw new Error('unmocked delete') }) as never)
  return { get, post, patch, del }
}
const next = (v: FlowView) => ({ data: (current = v) })

function renderPage(path = '/app/room-flow') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={qc}><MemoryRouter initialEntries={[path]}><RoomFlowPage /></MemoryRouter></QueryClientProvider>)
}

afterEach(() => vi.restoreAllMocks())

describe('start and resume', () => {
  it('offers to start when there is no active design, then shows the first question', async () => {
    const s = server(null)
    s.post.mockImplementation((async (url: string) => (url === '/room-flows/' ? next(GOAL) : undefined)) as never)
    renderPage()
    expect(await screen.findByText(t('rf.intro'))).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: t('rf.start') }))
    expect(await screen.findByText('goal title')).toBeInTheDocument()
    expect(screen.getByTestId('progress')).toHaveTextContent('Step 1 of 7')
    expect(screen.getByRole('button', { name: 'Kitchen' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: t('rf.back') })).not.toBeInTheDocument()     // no back on the first step
    expect(s.post).toHaveBeenCalledWith('/room-flows/')
  })

  it('resumes the active design at the step where the user stopped', async () => {
    server(SIZE)
    renderPage()
    expect(await screen.findByText('size title')).toBeInTheDocument()
    expect(screen.getByTestId('progress')).toHaveTextContent('Step 4 of 7')
    expect(screen.getByLabelText('Width (mm)')).toHaveValue(4000)
    expect(screen.getByLabelText('Room height (mm)')).toHaveValue(2700)
  })

  it('opens the design named in the address even without an active list', async () => {
    const s = server(ELEMENTS)
    renderPage('/app/room-flow?flow=9')
    expect(await screen.findByText('elements title')).toBeInTheDocument()
    expect(s.get).toHaveBeenCalledWith('/room-flows/9/')
  })

  it('shows an error state when the design cannot be loaded', async () => {
    server(SIZE).get.mockImplementation((async (url: string) => { if (url === '/room-flows/') return list(); throw new Error('boom') }) as never)
    renderPage('/app/room-flow?flow=9')
    expect(await screen.findByText(t('rf.loadErr'))).toBeInTheDocument()
  })
})

describe('steps', () => {
  it('picking an option answers the step', async () => {
    const s = server(GOAL)
    s.post.mockImplementation((async () => next(PHOTO)) as never)
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Kitchen' }))
    await waitFor(() => expect(s.post).toHaveBeenCalledWith('/room-flows/9/answer/', { step: 'goal', value: 'kitchen' }))
    expect(await screen.findByText('photo title')).toBeInTheDocument()
  })

  it('photo: skip', async () => {
    const s = server(PHOTO)
    s.post.mockImplementation((async () => next(ELEMENTS)) as never)
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: t('rf.skip') }))
    await waitFor(() => expect(s.post).toHaveBeenCalledWith('/room-flows/9/answer/', { step: 'photo', value: { skip: true } }))
  })

  it('photo: uploads to the gallery first, then answers with the image id', async () => {
    const s = server(PHOTO)
    s.post.mockImplementation((async (url: string) => (url === '/gallery/' ? { data: { id: 77 } } : next(ELEMENTS))) as never)
    const { container } = renderPage()
    await screen.findByText('photo title')
    fireEvent.change(container.querySelector('input[type=file]')!, { target: { files: [new File([new Uint8Array(8)], 'room.png', { type: 'image/png' })] } })
    await waitFor(() => expect(s.post).toHaveBeenCalledWith('/room-flows/9/answer/', { step: 'photo', value: { image_id: 77 } }))
    const fd = s.post.mock.calls.find((c) => c[0] === '/gallery/')![1] as FormData
    expect(fd.get('source')).toBe('room')
    expect((fd.get('image') as File).name).toBe('room.png')
  })

  it('elements: counts and furniture quantities are sent as the server expects them', async () => {
    const s = server(ELEMENTS)
    s.post.mockImplementation((async () => next(SIZE)) as never)
    renderPage()
    await screen.findByText('elements title')
    expect(screen.getByLabelText('Doors')).toHaveValue(1)
    fireEvent.change(screen.getByLabelText('Windows'), { target: { value: '3' } })
    fireEvent.click(screen.getByRole('button', { name: 'Bedside table +' }))
    fireEvent.click(screen.getByRole('button', { name: 'Bedside table +' }))
    fireEvent.click(screen.getByRole('button', { name: 'Dresser +' }))
    fireEvent.click(screen.getByRole('button', { name: 'Dresser -' }))     // back to zero: not sent
    fireEvent.click(screen.getByRole('button', { name: t('rf.next') }))
    await waitFor(() => expect(s.post).toHaveBeenCalledWith('/room-flows/9/answer/', { step: 'elements', value: { doors: 1, windows: 3, furniture: ['bedside', 'bedside'] } }))
  })

  it('size: sends numbers and shows the server message beside the field it belongs to', async () => {
    const s = server(SIZE)
    s.post.mockImplementation((async () => { throw fail(400, { width: ['must be between 1000 and 15000 mm'] }) }) as never)
    renderPage()
    fireEvent.change(await screen.findByLabelText('Width (mm)'), { target: { value: '999' } })
    fireEvent.click(screen.getByRole('button', { name: t('rf.next') }))
    await waitFor(() => expect(s.post).toHaveBeenCalledWith('/room-flows/9/answer/', { step: 'size', value: { width: 999, length: 3000, height: 2700 } }))
    expect(await screen.findByText('must be between 1000 and 15000 mm')).toBeInTheDocument()
    expect(screen.getByText('size title')).toBeInTheDocument()            // still on the same step
  })

  it('size: an empty field blocks the submit', async () => {
    const s = server(SIZE)
    renderPage()
    fireEvent.change(await screen.findByLabelText('Length (mm)'), { target: { value: '' } })
    expect(screen.getByRole('button', { name: t('rf.next') })).toBeDisabled()
    expect(s.post).not.toHaveBeenCalled()
  })

  it('openings: starts valid, lets the user pick walls, and shows per-opening server errors', async () => {
    const s = server(OPENINGS)
    s.post.mockImplementationOnce((async () => { throw fail(400, { 'openings.1.offset': ['opening does not fit'] }) }) as never)
    renderPage()
    await screen.findByText('openings title')
    const rows = [screen.getByTestId('opening-0'), screen.getByTestId('opening-1')]
    expect(within(rows[0]).getByText('Door 1')).toBeInTheDocument()
    expect(within(rows[1]).getByText('Window 1')).toBeInTheDocument()
    expect(within(rows[0]).getByLabelText(t('rf.height'))).toHaveValue(2100)
    expect(within(rows[1]).getByLabelText(t('rf.sill'))).toHaveValue(900)
    expect(within(rows[0]).queryByLabelText(t('rf.sill'))).not.toBeInTheDocument()       // a door starts at the floor
    fireEvent.change(within(rows[0]).getByLabelText(t('rf.wall')), { target: { value: 'south' } })
    expect(within(rows[0]).getByText('The wall is 4000 mm long')).toBeInTheDocument()
    fireEvent.change(within(rows[1]).getByLabelText(t('rf.offset')), { target: { value: '5000' } })
    fireEvent.click(screen.getByRole('button', { name: t('rf.next') }))
    expect(await within(rows[1]).findByText('opening does not fit')).toBeInTheDocument()
    expect(within(rows[0]).queryByText('opening does not fit')).not.toBeInTheDocument()
    s.post.mockImplementation((async () => next(view('style', 'choice', 6, { options: [] }))) as never)
    fireEvent.change(within(rows[1]).getByLabelText(t('rf.offset')), { target: { value: '800' } })
    fireEvent.click(screen.getByRole('button', { name: t('rf.next') }))
    await waitFor(() => expect(s.post).toHaveBeenLastCalledWith('/room-flows/9/answer/', { step: 'openings', value: [
      { type: 'door', wall: 'south', offset: 100, width: 900, height: 2100, sill: 0 }, { type: 'window', wall: 'east', offset: 800, width: 1200, height: 1200, sill: 900 }] }))
  })

  it('back goes to the previous step', async () => {
    const s = server(SIZE)
    s.post.mockImplementation((async () => next(ELEMENTS)) as never)
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: t('rf.back') }))
    await waitFor(() => expect(s.post).toHaveBeenCalledWith('/room-flows/9/back/'))
    expect(await screen.findByText('elements title')).toBeInTheDocument()
  })

  it('an out-of-date screen is replaced by the real step instead of showing an error', async () => {
    const s = server(GOAL)
    s.post.mockImplementation((async () => { current = SIZE; throw fail(409, { code: 'step_mismatch', expected: 'size' }) }) as never)
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Kitchen' }))
    expect(await screen.findByText('size title')).toBeInTheDocument()
  })
})

describe('closed designs', () => {
  it('an abandoned design offers a new one instead of a question', async () => {
    const s = server(view('size', 'number_group', 4, SIZE.descriptor, { status: 'abandoned' }))
    s.post.mockImplementation((async () => next(GOAL)) as never)
    renderPage('/app/room-flow?flow=9')
    expect(await screen.findByText(t('rf.closed'))).toBeInTheDocument()
    expect(screen.queryByLabelText('Width (mm)')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: t('rf.newDesign') }))
    await waitFor(() => expect(s.post).toHaveBeenCalledWith('/room-flows/'))
  })

  it('a completed design shows the saved summary with the disclaimer', async () => {
    server(view('done', 'summary', 7, {}, { status: 'completed', items: [ITEM, ITEM2] }))
    renderPage('/app/room-flow?flow=9')
    expect(await screen.findByText(t('rf.saved'))).toBeInTheDocument()
    expect(screen.getByText(t('rf.disclaimer'))).toBeInTheDocument()
    expect(screen.getByRole('link', { name: t('rf.openDesigns') })).toHaveAttribute('href', '/app/designs')
  })

  it('start over asks first, then abandons the design and starts another', async () => {
    const s = server(SIZE)
    s.post.mockImplementation((async (url: string) => (url.endsWith('/abandon/') ? next({ ...SIZE, status: 'abandoned' }) : next(GOAL))) as never)
    renderPage('/app/room-flow?flow=9')
    fireEvent.click(await screen.findByRole('button', { name: t('rf.startOver') }))
    expect(s.post).not.toHaveBeenCalled()
    fireEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: t('rf.startOverConfirm') }))
    await waitFor(() => expect(s.post).toHaveBeenCalledWith('/room-flows/9/abandon/'))
    await waitFor(() => expect(s.post).toHaveBeenCalledWith('/room-flows/'))
  })
})

describe('furnishing', () => {
  const result = (items: RoomItem[], rev: number, warnings: unknown[] = []) => ({ data: { rev, items, item: items[items.length - 1], warnings } })

  it('lists the items and adds furniture with the revision the user saw', async () => {
    const s = server(furnish([ITEM], 3))
    s.post.mockImplementation((async () => result([ITEM, ITEM2], 4)) as never)
    renderPage('/app/room-flow?flow=9')
    await screen.findByText('furnish title')
    expect(screen.getByRole('button', { name: '1. Bedside table' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Dresser' }))
    await waitFor(() => expect(s.post).toHaveBeenCalledWith('/room-flows/9/items/', { template: 'dresser', rev: 3 }))
    expect(await screen.findByRole('button', { name: '2. Dresser' })).toBeInTheDocument()
  })

  it('edits the selected item: apply, rotate and remove each carry the revision', async () => {
    const s = server(furnish([ITEM], 3))
    s.patch.mockImplementation((async () => result([{ ...ITEM, x: 600 }], 4)) as never)
    s.del.mockImplementation((async () => result([], 6)) as never)
    renderPage('/app/room-flow?flow=9')
    fireEvent.click(await screen.findByRole('button', { name: '1. Bedside table' }))
    expect(screen.getByRole('button', { name: t('rf.apply') })).toBeDisabled()          // nothing changed yet
    fireEvent.change(screen.getByLabelText('x (mm)'), { target: { value: '600' } })
    fireEvent.click(screen.getByRole('button', { name: t('rf.apply') }))
    await waitFor(() => expect(s.patch).toHaveBeenCalledWith(`/room-flows/9/items/${ITEM.id}/`, { x: 600, z: 0, width: 450, depth: 400, height: 500, rev: 3 }))
    await waitFor(() => expect(screen.getByLabelText('x (mm)')).toHaveValue(600))
    s.patch.mockImplementation((async () => result([{ ...ITEM, x: 600, rot: 90 }], 5)) as never)
    fireEvent.click(screen.getByRole('button', { name: t('rf.rotate') }))
    await waitFor(() => expect(s.patch).toHaveBeenLastCalledWith(`/room-flows/9/items/${ITEM.id}/`, { rot: 90, rev: 4 }))
    fireEvent.click(screen.getByRole('button', { name: t('rf.remove') }))
    await waitFor(() => expect(s.del).toHaveBeenCalledWith(`/room-flows/9/items/${ITEM.id}/`, { params: { rev: 5 } }))
    expect(await screen.findByText(t('rf.noItems'))).toBeInTheDocument()
  })

  it('a revision conflict reloads the room instead of overwriting it', async () => {
    const s = server(furnish([ITEM], 3))
    s.post.mockImplementation((async () => { current = furnish([ITEM, ITEM2], 5); throw fail(409, { code: 'rev_conflict', current_rev: 5 }) }) as never)
    renderPage('/app/room-flow?flow=9')
    await screen.findByText('furnish title')
    const before = s.get.mock.calls.filter((c) => c[0] === '/room-flows/9/').length
    fireEvent.click(screen.getByRole('button', { name: 'Bedside table' }))
    expect(await screen.findByRole('button', { name: '2. Dresser' })).toBeInTheDocument()          // the other device's furniture is now visible
    expect(s.get.mock.calls.filter((c) => c[0] === '/room-flows/9/').length).toBeGreaterThan(before)
  })

  it('translates server warnings and shows the disclaimer', async () => {
    server(furnish([ITEM], 3, { warnings: [{ code: 'door_zone', item: ITEM.id }, { code: 'not_placed', item: 'dresser' }, { code: 'items_reset' }] }))
    renderPage('/app/room-flow?flow=9')
    expect(await screen.findByText('Bedside table blocks the area in front of a door.')).toBeInTheDocument()
    expect(screen.getByText('Dresser did not fit in the room and was not placed.')).toBeInTheDocument()
    expect(screen.getByText(t('rf.warnReset'))).toBeInTheDocument()
    expect(screen.getByText(t('rf.disclaimer'))).toBeInTheDocument()
  })

  it('finishing answers the furnish step', async () => {
    const s = server(furnish([ITEM], 3))
    s.post.mockImplementation((async () => next(view('done', 'summary', 7, {}, { status: 'completed', items: [ITEM] }))) as never)
    renderPage('/app/room-flow?flow=9')
    fireEvent.click(await screen.findByRole('button', { name: t('rf.finish') }))
    await waitFor(() => expect(s.post).toHaveBeenCalledWith('/room-flows/9/answer/', { step: 'furnish', value: { done: true } }))
    expect(await screen.findByText(t('rf.saved'))).toBeInTheDocument()
  })
})

describe('language', () => {
  it('has every room-flow text in uz and ru', () => {
    for (const lang of ['uz', 'ru'] as const) for (const k of ['rf.nav', 'rf.start', 'rf.next', 'rf.finish', 'rf.disclaimer', 'rf.warnDoor', 'rf.conflict']) expect(translate(lang, k)).not.toBe(k)
  })
})
