import { fireEvent, screen, within } from '@testing-library/react'
import { api } from '../../lib/api'
import { order, workshop } from '../../test/fixtures'
import { httpError, page, renderApp, routeGet, signIn } from '../../test/utils'
import WorkshopDetail from './WorkshopDetail'

vi.mock('../../lib/api', async (orig) => ({ ...(await orig<typeof import('../../lib/api')>()), api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }))
beforeEach(() => { vi.clearAllMocks(); signIn() })
const stats = { workshop: 1, generated_at: '', orders: { total: 6, new: 1, confirmed: 1, in_production: 1, ready: 1, delivered: 1, cancelled: 1 }, employees: { total: 3, active: 2, invited: 1 },
  tasks: { total: 6, pending: 2, in_progress: 1, review: 1, completed: 1, cancelled: 1, overdue: 2 }, money: { total_order_value: '10600.00', paid_amount: '7600.00', outstanding_amount: '2500.00', note: '' } }
const mount = (ws = workshop(), url = '/app/workshops/1') => { routeGet({ '/workshops/1/': ws, '/workshops/1/statistics/': stats, '/orders/': page([order()]), '/tasks/': page([]), '/workshops/1/members/': page([]) }); return renderApp(<WorkshopDetail />, { path: '/app/workshops/:id', url }) }
const tabNames = () => within(screen.getByRole('tablist')).getAllByRole('tab').map((t) => t.textContent)

describe('WorkshopDetail', () => {
  it('the owner gets overview first, then orders, tasks, team and settings', async () => {
    mount()
    expect(await screen.findByRole('heading', { name: 'Alpha Workshop' })).toBeInTheDocument()
    expect(tabNames()).toEqual(['Overview', 'Orders', 'Tasks', 'Team', 'Settings'])
    expect(await screen.findByText('Order value')).toBeInTheDocument()
    expect(screen.getByText((10600).toLocaleString())).toBeInTheDocument(); expect(screen.getByText((2500).toLocaleString())).toBeInTheDocument()   // straight from the statistics endpoint
  })

  it('an employee has no overview or settings and never requests the statistics', async () => {
    mount(workshop({ my_role: 'employee' }))
    await screen.findByRole('heading', { name: 'Alpha Workshop' })
    expect(tabNames()).toEqual(['Orders', 'Tasks', 'Team'])
    expect(await screen.findByText('Kitchen set')).toBeInTheDocument()
    expect(vi.mocked(api.get).mock.calls.some((c) => String(c[0]).includes('statistics'))).toBe(false)
  })

  it('a hand-typed ?tab=settings cannot open owner-only content for an employee', async () => {
    mount(workshop({ my_role: 'employee' }), '/app/workshops/1?tab=settings')
    await screen.findByRole('heading', { name: 'Alpha Workshop' })
    expect(screen.queryByText('Danger zone')).not.toBeInTheDocument(); expect(screen.getByRole('tab', { name: 'Orders', selected: true })).toBeInTheDocument()
  })

  it('deep-links to a tab and switches tabs', async () => {
    mount(workshop(), '/app/workshops/1?tab=team')
    expect(await screen.findByRole('tab', { name: 'Team', selected: true })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: 'Orders' }))
    expect(await screen.findByText('Kitchen set')).toBeInTheDocument()
  })

  it('warns that an inactive or suspended workshop is read-only', async () => {
    const { unmount } = mount(workshop({ status: 'inactive' })); expect(await screen.findByText(/This workshop is inactive/)).toBeInTheDocument(); unmount()
    mount(workshop({ status: 'suspended' })); expect(await screen.findByText(/suspended by the platform administrators/)).toBeInTheDocument()
  })

  it('a workshop that does not exist (or is not yours) shows one neutral message', async () => {
    routeGet({ '/workshops/1/': httpError(404, { error: { status: 404, detail: 'Not found.' } }) }); renderApp(<WorkshopDetail />, { path: '/app/workshops/:id', url: '/app/workshops/1' })
    expect(await screen.findByRole('alert')).toHaveTextContent('does not exist or you are not a member')
  })
})
