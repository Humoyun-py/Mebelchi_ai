import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { api } from '../../lib/api'
import { member, order, task, workshop } from '../../test/fixtures'
import { httpError, page, renderApp, routeGet, signIn } from '../../test/utils'
import { TaskModal, TasksTab } from './TasksTab'

vi.mock('../../lib/api', async (orig) => ({ ...(await orig<typeof import('../../lib/api')>()), api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }))
beforeEach(() => { vi.clearAllMocks(); signIn(); vi.mocked(api.patch).mockResolvedValue({ data: {} } as never); vi.mocked(api.post).mockResolvedValue({ data: task() } as never); vi.mocked(api.delete).mockResolvedValue({ data: {} } as never) })
const ws = workshop()
const base = (t = task(), extra: Record<string, unknown> = {}) => ({ '/tasks/': page([t]), [`/tasks/${t.id}/`]: t, '/orders/': page([order(), order({ id: 101, order_number: 'ORD-0001-000002', title: 'Finished job', status: 'delivered' })]),
  '/workshops/1/members/': page([member()]), ...extra })

describe('TasksTab', () => {
  it('lists tasks with assignee, priority and deadline; overdue ones are marked', async () => {
    routeGet(base(task({ is_overdue: true, deadline: '2026-01-01T10:00:00Z', priority: 'urgent', status: 'in_progress', allowed_next_statuses: ['review'] })))
    renderApp(<TasksTab ws={ws} owner writable />)
    const table = within(await screen.findByRole('table'))
    expect(table.getByText('Cut panels')).toBeInTheDocument(); expect(table.getAllByText('Aziz Karimov').length).toBeGreaterThan(0); expect(table.getByText('Urgent')).toBeInTheDocument(); expect(table.getAllByText('In progress').length).toBeGreaterThan(0)
    expect(document.querySelector('td .text-danger')).not.toBeNull()
  })

  it('the quick action button moves the task along and never offers "cancelled" inline', async () => {
    routeGet(base(task({ allowed_next_statuses: ['cancelled', 'in_progress'] })))
    renderApp(<TasksTab ws={ws} owner writable />)
    const btn = await screen.findByRole('button', { name: 'Cut panels: In progress' })
    expect(screen.queryByRole('button', { name: /Cut panels: Cancelled/ })).not.toBeInTheDocument()
    fireEvent.click(btn)
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/tasks/200/', { status: 'in_progress' }))
  })

  it('an employee has no assignee filter, no mine switch, no create button', async () => {
    routeGet(base()); renderApp(<TasksTab ws={workshop({ my_role: 'employee' })} owner={false} writable />)
    await screen.findByText('Cut panels')
    expect(screen.queryByRole('button', { name: /New task/ })).not.toBeInTheDocument(); expect(screen.queryByLabelText('Assigned to')).not.toBeInTheDocument(); expect(screen.queryByRole('switch', { name: 'Assigned to me' })).not.toBeInTheDocument()
    const params = vi.mocked(api.get).mock.calls.find((c) => c[0] === '/tasks/')![1]!.params as Record<string, unknown>
    expect(params).not.toHaveProperty('assigned_to')
  })

  it('shows what the server says is allowed and nothing when it says nothing (read-only workshop)', async () => {
    routeGet(base(task({ allowed_next_statuses: [] }))); renderApp(<TasksTab ws={ws} owner writable />)
    await screen.findByText('Cut panels'); expect(within(screen.getByRole('table')).queryByRole('button')).not.toBeInTheDocument()
  })

  it('empty states differ for owner, employee and filtered lists', async () => {
    routeGet(base(task(), { '/tasks/': page([]) }))
    const { unmount } = renderApp(<TasksTab ws={ws} owner writable />)
    expect(await screen.findByText('Create tasks and assign them to employees.')).toBeInTheDocument(); unmount()
    routeGet(base(task(), { '/tasks/': page([]) })); const r = renderApp(<TasksTab ws={workshop({ my_role: 'employee' })} owner={false} writable />)
    expect(await screen.findByText('Tasks assigned to you appear here.')).toBeInTheDocument(); r.unmount()
    routeGet(base(task(), { '/tasks/': page([]) })); renderApp(<TasksTab ws={ws} owner writable />)
    fireEvent.change(await screen.findByLabelText('Priority'), { target: { value: 'urgent' } })
    expect(await screen.findByText('No tasks match these filters')).toBeInTheDocument()
  })

  it('reports a load failure with the server message', async () => {
    routeGet(base(task(), { '/tasks/': httpError(500, { error: { status: 500, detail: 'Boom.' } }) })); renderApp(<TasksTab ws={ws} owner writable />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Boom.')
  })
})

describe('TaskModal', () => {
  it('creates a task: only open orders are offered; the deadline is sent as ISO; the workshop is included', async () => {
    routeGet(base()); const onClose = vi.fn()
    renderApp(<TaskModal ws={ws} owner writable taskId={null} onClose={onClose} />)
    await screen.findByRole('option', { name: /ORD-0001-000001/ })
    expect(screen.queryByRole('option', { name: /ORD-0001-000002/ })).not.toBeInTheDocument()   // delivered orders cannot take tasks
    fireEvent.change(screen.getByLabelText('Task'), { target: { value: 'Edge banding' } })
    fireEvent.change(screen.getByLabelText('Order'), { target: { value: '100' } }); fireEvent.change(screen.getByLabelText('Assigned to'), { target: { value: '10' } })
    fireEvent.change(screen.getByLabelText('Priority'), { target: { value: 'high' } }); fireEvent.change(screen.getByLabelText('Deadline'), { target: { value: '2030-05-01T09:30' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(api.post).toHaveBeenCalled())
    const [url, body] = vi.mocked(api.post).mock.calls[0] as [string, Record<string, unknown>]
    expect(url).toBe('/tasks/'); expect(body).toMatchObject({ title: 'Edge banding', workshop: 1, order: 100, assigned_to: 10, priority: 'high' })
    expect(new Date(body.deadline as string).toISOString()).toBe(new Date('2030-05-01T09:30').toISOString())
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })

  it('a task opened from an order is locked to that order', async () => {
    routeGet(base()); renderApp(<TaskModal ws={ws} owner writable taskId={null} orderId={100} onClose={vi.fn()} />)
    await screen.findByRole('option', { name: /ORD-0001-000001/ }); expect(screen.getByLabelText('Order')).toBeDisabled(); expect(screen.getByLabelText('Order')).toHaveValue('100')
  })

  it('shows server validation errors and keeps the dialog open', async () => {
    vi.mocked(api.post).mockRejectedValue(httpError(400, { error: { status: 400, detail: 'Validation failed.', fields: { deadline: ['The deadline must be in the future.'] } } }))
    routeGet(base()); const onClose = vi.fn(); renderApp(<TaskModal ws={ws} owner writable taskId={null} onClose={onClose} />)
    fireEvent.change(await screen.findByLabelText('Task'), { target: { value: 'x' } }); fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('The deadline must be in the future.')).toBeInTheDocument(); expect(onClose).not.toHaveBeenCalled()
  })

  it('an assignee only gets a read-only view plus the server-approved status buttons', async () => {
    routeGet(base(task({ allowed_next_statuses: ['in_progress'], description: 'Use 18 mm board' })))
    renderApp(<TaskModal ws={workshop({ my_role: 'employee' })} owner={false} writable taskId={200} onClose={vi.fn()} />)
    const region = within(await screen.findByRole('region', { name: 'Update status' }))
    expect(screen.queryByLabelText('Task')).not.toBeInTheDocument(); expect(screen.queryByRole('button', { name: 'Save' })).not.toBeInTheDocument(); expect(screen.queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument()
    expect(screen.getByText('Use 18 mm board')).toBeInTheDocument()
    fireEvent.change(region.getByLabelText('Note (optional)'), { target: { value: 'Starting now' } }); fireEvent.click(region.getByRole('button', { name: 'In progress' }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/tasks/200/', { status: 'in_progress', status_note: 'Starting now' }))
  })

  it('editing does not resend an unchanged deadline (it may already be in the past)', async () => {
    routeGet(base(task({ deadline: '2020-01-01T10:00:00Z', is_overdue: true }))); renderApp(<TaskModal ws={ws} owner writable taskId={200} onClose={vi.fn()} />)
    fireEvent.change(await screen.findByLabelText('Priority'), { target: { value: 'urgent' } }); fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(api.patch).toHaveBeenCalled())
    expect(vi.mocked(api.patch).mock.calls[0][1]).not.toHaveProperty('deadline'); expect(vi.mocked(api.patch).mock.calls[0][1]).toMatchObject({ priority: 'urgent' })
  })

  it('final tasks are read-only; only never-started tasks can be deleted, after a confirmation', async () => {
    routeGet(base(task({ status: 'completed', allowed_next_statuses: [], started_at: '2026-03-02T00:00:00Z' }))); const done = renderApp(<TaskModal ws={ws} owner writable taskId={200} onClose={vi.fn()} />)
    await screen.findByText('Cut panels'); expect(screen.queryByRole('button', { name: 'Save' })).not.toBeInTheDocument(); expect(screen.queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument(); done.unmount()
    routeGet(base()); renderApp(<TaskModal ws={ws} owner writable taskId={200} onClose={vi.fn()} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Delete' })); expect(api.delete).not.toHaveBeenCalled()
    fireEvent.click(within(await screen.findByRole('dialog', { name: 'Delete this task?' })).getByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(api.delete).toHaveBeenCalledWith('/tasks/200/'))
  })

  it('renders the status history', async () => {
    routeGet(base(task({ status: 'review', status_history: [
      { id: 1, from_status: '', to_status: 'pending', changed_by: { id: 1, full_name: 'Me User' }, note: 'Task created', created_at: '2026-03-01T00:00:00Z' },
      { id: 2, from_status: 'pending', to_status: 'in_progress', changed_by: { id: 2, full_name: 'Aziz Karimov' }, note: '', created_at: '2026-03-02T00:00:00Z' }] })))
    renderApp(<TaskModal ws={ws} owner writable taskId={200} onClose={vi.fn()} />)
    const hist = within(await screen.findByRole('region', { name: 'History' })); expect(hist.getByText(/Task created/)).toBeInTheDocument(); expect(hist.getByText(/Aziz Karimov/)).toBeInTheDocument()
  })
})
