import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { api } from '../../lib/api'
import { httpError, page, renderApp, routeGet, signIn } from '../../test/utils'
import Admin from './Admin'

vi.mock('../../lib/api', async (orig) => ({ ...(await orig<typeof import('../../lib/api')>()), api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }))
beforeEach(() => { vi.clearAllMocks(); signIn({ is_admin: true }); vi.mocked(api.post).mockResolvedValue({ data: {} } as never); vi.mocked(api.patch).mockResolvedValue({ data: {} } as never) })

const ws = (o: Record<string, unknown> = {}) => ({ id: 7, name: 'Samarkand Furniture', kind: 'workshop', city: 'Samarkand', slug: 'samarkand-furniture', status: 'pending', review_note: '', owner: 3, owner_email: 'owner@x.com',
  member_count: 1, order_count: 0, created_at: '2026-03-01T10:00:00Z', updated_at: '2026-03-01T10:00:00Z', ...o })
const stats = { users: { total: 1, active_30d: 1, by_role: [] }, projects: { total: 0, active: 0 }, subscriptions: [], payments: { pending: 0, paid: 0, revenue_usd: '0' }, storage_bytes: 0, signups_14d: [], usage_14d: [], errors_24h: 0 }
const open = async (rows: unknown[] = [ws()], extra: Record<string, unknown> = {}) => {
  routeGet({ '/admin-api/stats/': stats, '/admin-api/workshops/': page(rows), ...extra })
  renderApp(<Admin />); fireEvent.click(await screen.findByRole('tab', { name: 'Workshops' })); await screen.findAllByRole('table')
  await screen.findByText(rows.length > 1 ? 'Missing address' : 'Samarkand Furniture')
}
const lastParams = (url: string) => vi.mocked(api.get).mock.calls.filter((c) => c[0] === url).at(-1)![1]!.params as Record<string, unknown>

describe('Admin → Workshops', () => {
  it('opens on the pending applications and sends every filter to the server', async () => {
    await open()
    expect(lastParams('/admin-api/workshops/')).toMatchObject({ status: 'pending' })
    expect(screen.getByText('owner@x.com')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'rejected' } })
    await waitFor(() => expect(lastParams('/admin-api/workshops/')).toMatchObject({ status: 'rejected', page: 1 }))
    fireEvent.change(screen.getByLabelText('Search workshop or owner'), { target: { value: 'samar' } })
    await waitFor(() => expect(lastParams('/admin-api/workshops/')).toMatchObject({ search: 'samar' }))
  })

  it('approves with one click through the approve endpoint', async () => {
    await open()
    fireEvent.click(screen.getByRole('button', { name: 'Approve Samarkand Furniture' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/admin-api/workshops/7/approve/', {}))
  })

  it('rejecting needs a reason, then sends it', async () => {
    await open()
    fireEvent.click(screen.getByRole('button', { name: 'Reject Samarkand Furniture' }))
    const dialog = within(await screen.findByRole('dialog'))
    const submit = dialog.getByRole('button', { name: 'Reject application' })
    expect(submit).toBeDisabled(); expect(api.post).not.toHaveBeenCalled()
    fireEvent.change(dialog.getByLabelText('Reason (shown to the owner)'), { target: { value: 'Phone does not work' } })
    expect(submit).toBeEnabled(); fireEvent.click(submit)
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/admin-api/workshops/7/reject/', { note: 'Phone does not work' }))
  })

  it('shows the server refusal inside the dialog instead of closing it', async () => {
    vi.mocked(api.post).mockRejectedValue(httpError(400, { error: { status: 400, detail: 'Validation failed.', fields: { note: ['Tell the owner why the application is rejected.'] } } }))
    await open()
    fireEvent.click(screen.getByRole('button', { name: 'Reject Samarkand Furniture' }))
    const dialog = within(await screen.findByRole('dialog'))
    fireEvent.change(dialog.getByLabelText('Reason (shown to the owner)'), { target: { value: 'x' } }); fireEvent.click(dialog.getByRole('button', { name: 'Reject application' }))
    expect(await dialog.findByRole('alert')).toHaveTextContent(/why the application is rejected/)
  })

  it('offers only the moves the server allows for each status and shows the stored reason', async () => {
    await open([ws({ id: 1, name: 'A', status: 'rejected', review_note: 'Missing address' }), ws({ id: 2, name: 'B', status: 'active' }), ws({ id: 3, name: 'C', status: 'suspended' })], {})
    expect(await screen.findByText('Missing address')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Approve anyway A' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Reject A' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Suspend B' })).toBeInTheDocument(); expect(screen.queryByRole('button', { name: 'Approve B' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reactivate C' })).toBeInTheDocument()
  })

  it('shows the audit history of one workshop', async () => {
    await open([ws()], { '/admin-api/audit-logs/': page([
      { id: 2, created_at: '2026-03-02T10:00:00Z', actor: 1, actor_email: 'admin@x.com', action: 'update', action_label: 'Updated', event: 'workshop.rejected', model: 'workshops.workshop', object_id: '7', object_repr: 'x',
        changes: { status: { old: 'pending', new: 'rejected' }, review_note: { old: '', new: 'Phone does not work' } }, ip: null, method: 'POST', path: '' }]) })
    fireEvent.click(screen.getByRole('button', { name: 'History Samarkand Furniture' }))
    const list = within(await screen.findByRole('list', { name: 'Workshop history' }))
    expect(list.getByText('workshop.rejected')).toBeInTheDocument(); expect(list.getByText('admin@x.com')).toBeInTheDocument()
    expect(list.getByText(/pending → rejected/)).toBeInTheDocument(); expect(list.getByText(/Phone does not work/)).toBeInTheDocument()
    expect(lastParams('/admin-api/audit-logs/')).toMatchObject({ model: 'workshops.workshop', object_id: 7 })
  })

  it('administrators change a user role from the Users tab', async () => {
    routeGet({ '/admin-api/stats/': stats, '/admin-api/users/': page([{ id: 9, email: 'u@x.com', first_name: 'U', last_name: 'X', role: 'maker', is_active: true, is_staff: false, date_joined: '2026-01-01T00:00:00Z', plan: 'free', project_count: 0 }]) })
    renderApp(<Admin />); fireEvent.click(await screen.findByRole('tab', { name: 'Users' }))
    fireEvent.change(await screen.findByLabelText('Role u@x.com'), { target: { value: 'workshop' } })
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/admin-api/users/9/', { role: 'workshop' }))
  })
})
