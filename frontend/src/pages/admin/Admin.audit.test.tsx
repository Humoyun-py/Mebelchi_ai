import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { api } from '../../lib/api'
import type { AuditEntry } from '../../lib/types'
import { httpError, page, renderApp, routeGet, signIn } from '../../test/utils'
import Admin from './Admin'

vi.mock('../../lib/api', async (orig) => ({ ...(await orig<typeof import('../../lib/api')>()), api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }))
beforeEach(() => { vi.clearAllMocks(); signIn({ is_admin: true }) })
const entry = (o: Partial<AuditEntry> = {}): AuditEntry => ({ id: 1, created_at: '2026-03-01T10:00:00Z', actor: 1, actor_email: 'owner@a.com', action: 'update', action_label: 'Updated', event: 'order.status_changed', model: 'workshops.order',
  object_id: '5', object_repr: 'ORD-0001-000005', changes: { status: { old: 'new', new: 'confirmed' }, customer_phone: { old: '[redacted]', new: '[redacted]' } }, ip: '203.0.113.5', method: 'PATCH', path: '/api/v1/orders/5/', ...o })
const stats = { users: { total: 1, active_30d: 1, by_role: [] }, projects: { total: 0, active: 0 }, subscriptions: [], payments: { pending: 0, paid: 0, revenue_usd: '0' }, storage_bytes: 0, signups_14d: [], usage_14d: [], errors_24h: 0 }
const openAudit = async (rows: AuditEntry[] | Error = [entry()]) => { routeGet({ '/admin-api/stats/': stats, '/admin-api/audit-logs/': rows instanceof Error ? rows : page(rows) }); renderApp(<Admin />); fireEvent.click(await screen.findByRole('tab', { name: 'Audit log' })) }

describe('Admin audit log tab', () => {
  it('shows who did what to which object, with the redacted values intact', async () => {
    await openAudit()
    const table = within(await screen.findByRole('table'))
    expect(table.getByText('owner@a.com')).toBeInTheDocument(); expect(table.getByText('order.status_changed')).toBeInTheDocument(); expect(table.getByText('ORD-0001-000005')).toBeInTheDocument()
    expect(table.getByText('workshops.order #5')).toBeInTheDocument(); expect(table.getByText('203.0.113.5')).toBeInTheDocument()
    fireEvent.click(table.getByText('2 fields'))
    expect(table.getByText(/"new" → "confirmed"/)).toBeInTheDocument(); expect(table.getAllByText(/"\[redacted\]" → "\[redacted\]"/).length).toBe(1)
  })

  it('sends every filter to the server and nothing is editable', async () => {
    await openAudit(); await screen.findByRole('table')
    fireEvent.change(screen.getByLabelText('Action'), { target: { value: 'delete' } })
    fireEvent.change(screen.getByLabelText('Event (e.g. order.status_changed)'), { target: { value: 'task.assigned' } })
    fireEvent.change(screen.getByLabelText('Actor email'), { target: { value: 'boss@x.com' } })
    await waitFor(() => { const p = vi.mocked(api.get).mock.calls.filter((c) => c[0] === '/admin-api/audit-logs/').at(-1)![1]!.params as Record<string, unknown>; expect(p).toMatchObject({ action: 'delete', event: 'task.assigned', actor_email: 'boss@x.com' }) })
    expect(screen.queryByRole('button', { name: /delete|edit|save/i })).not.toBeInTheDocument()
  })

  it('system actions have no actor, empty results and errors are explained', async () => {
    await openAudit([entry({ actor: null, actor_email: '', changes: {} })])
    expect(await screen.findByText('system')).toBeInTheDocument(); expect(screen.queryByText(/fields?$/)).not.toBeInTheDocument()
  })
  it('empty list', async () => { await openAudit([]); expect(await screen.findByText('No audit entries match.')).toBeInTheDocument() })
  it('error state', async () => { await openAudit(httpError(500, {})); expect(await screen.findByRole('alert')).toHaveTextContent('Could not load the audit log.') })
})
