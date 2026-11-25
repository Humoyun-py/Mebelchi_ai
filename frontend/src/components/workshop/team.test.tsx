import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { api } from '../../lib/api'
import { member, person, workshop } from '../../test/fixtures'
import { httpError, page, renderApp, routeGet, signIn } from '../../test/utils'
import { TeamTab } from './TeamTab'

vi.mock('../../lib/api', async (orig) => ({ ...(await orig<typeof import('../../lib/api')>()), api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }))
beforeEach(() => { vi.clearAllMocks(); signIn({ id: 1 }); vi.mocked(api.patch).mockResolvedValue({ data: {} } as never); vi.mocked(api.post).mockResolvedValue({ data: {} } as never); vi.mocked(api.delete).mockResolvedValue({ data: {} } as never) })
const ws = workshop()
const owner = member({ id: 9, role: 'owner', user: person(1, 'Me User', 'me@x.com') })
const team = (rows = [owner, member(), member({ id: 11, user: person(3, 'Dilnoza Yusupova', 'dil@x.com'), status: 'invited', joined_at: null })]) => routeGet({ '/workshops/1/members/': page(rows) })

describe('TeamTab (owner)', () => {
  it('lists everyone with emails and statuses, and offers removal only for employees', async () => {
    team(); renderApp(<TeamTab ws={ws} owner writable />)
    const table = within(await screen.findByRole('table'))
    expect(table.getByText('aziz@x.com')).toBeInTheDocument(); expect(table.getByText('Invited')).toBeInTheDocument()
    expect(table.getByRole('button', { name: 'Remove: Aziz Karimov' })).toBeInTheDocument(); expect(table.queryByRole('button', { name: /Remove: Me User/ })).not.toBeInTheDocument()
    expect(table.queryByRole('button', { name: /Make owner: Me User/ })).not.toBeInTheDocument()
    expect(table.queryByRole('button', { name: /Make owner: Dilnoza/ })).not.toBeInTheDocument()     // an invited person cannot become owner
  })

  it('invites by email and shows the server\'s reason when it fails', async () => {
    team(); renderApp(<TeamTab ws={ws} owner writable />)
    const invite = await screen.findByRole('button', { name: 'Invite' }); expect(invite).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Email of an existing account'), { target: { value: 'new@x.com' } }); fireEvent.click(invite)
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/workshops/1/members/', { email: 'new@x.com' }))
    vi.mocked(api.post).mockRejectedValue(httpError(400, { error: { status: 400, detail: 'Validation failed.', fields: { email: ['No active MEBELCHI AI account uses this email.'] } } }))
    fireEvent.change(screen.getByLabelText('Email of an existing account'), { target: { value: 'ghost@x.com' } }); fireEvent.click(invite)
    expect(await screen.findByText('No active MEBELCHI AI account uses this email.')).toBeInTheDocument()
  })

  it('removing needs a confirmation that names the person', async () => {
    team(); renderApp(<TeamTab ws={ws} owner writable />)
    fireEvent.click(await screen.findByRole('button', { name: 'Remove: Aziz Karimov' })); expect(api.delete).not.toHaveBeenCalled()
    const dlg = await screen.findByRole('dialog', { name: 'Remove this member?' }); expect(dlg).toHaveTextContent('Aziz Karimov loses access')
    fireEvent.click(within(dlg).getByRole('button', { name: 'Remove' }))
    await waitFor(() => expect(api.delete).toHaveBeenCalledWith('/workshops/1/members/10/'))
  })

  it('transferring ownership sends the explicit confirmation flag only after the dialog', async () => {
    team(); renderApp(<TeamTab ws={ws} owner writable />)
    fireEvent.click(await screen.findByRole('button', { name: 'Make owner: Aziz Karimov' })); expect(api.patch).not.toHaveBeenCalled()
    fireEvent.click(within(await screen.findByRole('dialog', { name: 'Transfer ownership?' })).getByRole('button', { name: 'Transfer' }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/workshops/1/members/10/', { role: 'owner', confirm_transfer: true }))
  })

  it('an inactive workshop hides invitations and member actions', async () => {
    team(); renderApp(<TeamTab ws={workshop({ status: 'inactive' })} owner writable={false} />)
    await screen.findByRole('table'); expect(screen.queryByRole('button', { name: 'Invite' })).not.toBeInTheDocument(); expect(screen.queryByRole('button', { name: /Remove:/ })).not.toBeInTheDocument()
  })

  it('filters by status on the server', async () => {
    team(); renderApp(<TeamTab ws={ws} owner writable />)
    fireEvent.change(await screen.findByLabelText('Status'), { target: { value: 'removed' } })
    await waitFor(() => expect(vi.mocked(api.get).mock.calls.some((c) => (c[1]!.params as Record<string, unknown>).status === 'removed')).toBe(true))
  })
})

describe('TeamTab (employee)', () => {
  it('sees the roster without invite form, owner actions or status filter, and can leave', async () => {
    signIn({ id: 2 }); team([owner, member({ user: person(2, 'Aziz Karimov', 'aziz@x.com') }), member({ id: 12, user: person(4, 'Colleague', undefined) })])
    renderApp(<TeamTab ws={workshop({ my_role: 'employee' })} owner={false} writable />)
    const table = within(await screen.findByRole('table'))
    expect(screen.queryByRole('button', { name: 'Invite' })).not.toBeInTheDocument(); expect(screen.queryByLabelText('Status')).not.toBeInTheDocument()
    expect(table.queryByRole('button', { name: /Remove:|Make owner:/ })).not.toBeInTheDocument(); expect(table.getByText('(you)')).toBeInTheDocument()
    expect(table.queryByText('colleague@x.com')).not.toBeInTheDocument(); expect(screen.getByText('You see the names of active colleagues only.')).toBeInTheDocument()
    fireEvent.click(table.getByRole('button', { name: 'Leave' }))
    fireEvent.click(within(await screen.findByRole('dialog', { name: 'Leave this workshop?' })).getByRole('button', { name: 'Leave' }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/workshops/1/members/10/', { status: 'removed' }))
  })
})
