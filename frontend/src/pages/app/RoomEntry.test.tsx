import { screen, waitFor } from '@testing-library/react'
import { fireEvent } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { api } from '../../lib/api'
import { httpError, page, routeGet, signIn } from '../../test/utils'
import { LegacyInterior, RoomImport, RoomStart } from './RoomEntry'
import Home from './Home'
import Designs from './Designs'

vi.mock('../../lib/api', async (orig) => ({ ...(await orig<typeof import('../../lib/api')>()), api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }))
beforeEach(() => { vi.clearAllMocks(); signIn({ role: 'homeowner' }) })

const Where = () => { const l = useLocation(); return <div data-testid="where">{l.pathname}{l.search}</div> }
function mount(url: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={qc}><MemoryRouter initialEntries={[url]}><Routes>
    <Route path="/app/interior" element={<LegacyInterior />} /><Route path="/app/rooms/new" element={<RoomStart />} /><Route path="/app/rooms/import/:designId" element={<RoomImport />} />
    <Route path="/app" element={<Home />} /><Route path="/app/designs" element={<Designs />} /><Route path="*" element={<Where />} /></Routes></MemoryRouter></QueryClientProvider>)
}
const flowOf = (id: number) => ({ id, status: 'active', step: 'furnish', answers: {}, question: {}, design: 9, room: null, created_at: '', updated_at: '' })

describe('old /app/interior addresses', () => {
  it('opens a saved design through the importer', async () => { mount('/app/interior?design=12'); await waitFor(() => expect(screen.getByRole('status')).toBeInTheDocument()) })
  it('maps ?design to /rooms/import', async () => {
    vi.mocked(api.post).mockReturnValue(new Promise(() => {}))
    mount('/app/interior?design=12'); await waitFor(() => expect(api.post).toHaveBeenCalledWith('/rooms/import-design/', { design: 12 }))
  })
  it('maps ?room=kitchen to a new design with that goal and ?style / bare URL to the list', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: flowOf(30) } as never)
    mount('/app/interior?room=kitchen')
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/app/rooms/30'))
    expect(api.post).toHaveBeenNthCalledWith(1, '/rooms/'); expect(api.post).toHaveBeenNthCalledWith(2, '/rooms/30/answer/', { step: 'goal', value: 'kitchen' })
  })
  it.each(['/app/interior', '/app/interior?style=modern', '/app/interior?room=garage', '/app/interior?design=abc'])('never lands on an error page: %s', async (u) => {
    mount(u); await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/app/rooms'))
  })
})

describe('start a new room design from a link', () => {
  it('starts exactly once, goes to the design and survives a failed goal answer', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({ data: flowOf(31) } as never).mockRejectedValueOnce(httpError(409, { error: { status: 409, detail: 'x' } }))
    mount('/app/rooms/new?goal=office')
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/app/rooms/31'))
    expect(vi.mocked(api.post).mock.calls.filter((c) => c[0] === '/rooms/')).toHaveLength(1)
  })
  it('ignores an unknown goal', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: flowOf(32) } as never)
    mount('/app/rooms/new?goal=garage'); await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/app/rooms/32'))
    expect(api.post).toHaveBeenCalledTimes(1)
  })
  it('shows the server message when it cannot start', async () => {
    vi.mocked(api.post).mockRejectedValue(httpError(409, { error: { status: 409, detail: 'You have 20 unfinished room designs.' } }))
    mount('/app/rooms/new'); expect(await screen.findByText(/20 unfinished/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'All room designs' })).toHaveAttribute('href', '/app/rooms')
  })
})

describe('open an old design in the room designer', () => {
  it('shows a loading state, then opens the imported design', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: flowOf(40) } as never)
    mount('/app/rooms/import/12'); expect(screen.getByRole('status')).toHaveTextContent('Opening your design')
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/app/rooms/40'))
    expect(api.post).toHaveBeenCalledWith('/rooms/import-design/', { design: 12 })
  })
  it('imports once even though the page renders twice', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: flowOf(40) } as never)
    mount('/app/rooms/import/12'); await waitFor(() => expect(screen.getByTestId('where')).toBeInTheDocument())
    expect(api.post).toHaveBeenCalledTimes(1)
  })
  it('explains which old field blocks the import and says the old design is unchanged', async () => {
    vi.mocked(api.post).mockRejectedValue(httpError(400, { error: { status: 400, detail: 'Validation failed.', fields: { roomW: ['must be between 1000 and 15000 mm'] } } }))
    mount('/app/rooms/import/12')
    expect(await screen.findByText(/roomW: must be between 1000 and 15000 mm/)).toBeInTheDocument()
    expect(screen.getByText('Your original design is unchanged.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to my designs' })).toHaveAttribute('href', '/app/designs')
  })
  it('says not found for somebody else\'s design', async () => {
    vi.mocked(api.post).mockRejectedValue(httpError(404, { error: { status: 404, detail: 'Not found.' } }))
    mount('/app/rooms/import/99'); expect(await screen.findByText(/could not be opened/)).toBeInTheDocument()
  })
  it('a nonsense id goes to the designs list without calling the server', async () => {
    mount('/app/rooms/import/abc'); await waitFor(() => expect(api.get).toHaveBeenCalled())
    expect(api.post).not.toHaveBeenCalled()
  })
})

describe('Home and Designs point to the room designer', () => {
  it.each([['Design My Kitchen', 'kitchen'], ['Design My Bedroom', 'bedroom'], ['Design My Living Room', 'living'], ['Modern Style', null], ['Luxury Style', null]])('Home "%s" starts a room design%s', async (title, goal) => {
    vi.mocked(api.post).mockResolvedValue({ data: flowOf(50) } as never); routeGet({})
    mount('/app'); fireEvent.click(screen.getByText(title))
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/app/rooms/50'))
    expect(api.post).toHaveBeenCalledWith('/rooms/')
    if (goal) expect(api.post).toHaveBeenCalledWith('/rooms/50/answer/', { step: 'goal', value: goal }); else expect(api.post).toHaveBeenCalledTimes(1)
  })
  const d = (o: object) => ({ id: 1, name: 'D', kind: 'interior', project: null, config: {}, room_image: null, room_flow: null, updated_at: new Date().toISOString(), ...o })
  it('a room design opens its flow; an old interior design opens through the importer; a furniture design still opens the editor', async () => {
    routeGet({ '/designs/': page([d({ id: 1, name: 'New one', room_flow: 7 }), d({ id: 2, name: 'Old one' }), d({ id: 3, name: 'Cabinet', kind: 'furniture' })]) })
    mount('/app/designs')
    fireEvent.click(await screen.findByText('Old one')); await waitFor(() => expect(api.post).toHaveBeenCalledWith('/rooms/import-design/', { design: 2 }))
  })
  it('opens the saved room design directly', async () => {
    routeGet({ '/designs/': page([d({ id: 1, name: 'New one', room_flow: 7 })]) })
    mount('/app/designs'); fireEvent.click(await screen.findByText('New one'))
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/app/rooms/7'))
  })
  it('opens a furniture design in the editor', async () => {
    routeGet({ '/designs/': page([d({ id: 3, name: 'Cabinet', kind: 'furniture' })]) })
    mount('/app/designs'); fireEvent.click(await screen.findByText('Cabinet'))
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/app/editor?design=3'))
  })
})
