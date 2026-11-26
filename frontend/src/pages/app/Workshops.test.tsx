import { fireEvent, screen, waitFor } from '@testing-library/react'
import { api } from '../../lib/api'
import { invitation, workshop } from '../../test/fixtures'
import { httpError, page, renderApp, routeGet, signIn } from '../../test/utils'
import Workshops from './Workshops'

vi.mock('../../lib/api', async (orig) => ({ ...(await orig<typeof import('../../lib/api')>()), api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }))
beforeEach(() => { vi.clearAllMocks(); signIn() })

describe('Workshops page', () => {
  it('lists the workshops with status and role', async () => {
    routeGet({ '/workshops/': page([workshop(), workshop({ id: 2, name: 'Gamma', my_role: 'employee', status: 'inactive', owner: { id: 9, full_name: 'Other Owner' } })]), '/workshop-invitations/': page([]) })
    renderApp(<Workshops />)
    expect(await screen.findByText('Alpha Workshop')).toBeInTheDocument()
    expect(screen.getByText('Gamma')).toBeInTheDocument(); expect(screen.getByText('Inactive')).toBeInTheDocument(); expect(screen.getByText('Employee')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Alpha Workshop/ })).toHaveAttribute('href', '/app/workshops/1')
  })

  it('shows a loading skeleton, then an error with a working retry', async () => {
    let fail = true
    routeGet({ '/workshops/': () => (fail ? httpError(500, {}) : page([workshop()])), '/workshop-invitations/': page([]) })
    renderApp(<Workshops />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load your workshops.')
    fail = false; fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('Alpha Workshop')).toBeInTheDocument()
  })

  it('an empty list invites a workshop account to create a workshop', async () => {
    signIn({ role: 'workshop' })
    routeGet({ '/workshops/': page([]), '/workshop-invitations/': page([]) })
    renderApp(<Workshops />)
    expect(await screen.findByText('No workshops yet')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /New workshop/ }).length).toBeGreaterThan(0)
  })

  it.each(['homeowner', 'maker'] as const)('a %s account cannot create workshops and is told why', async (role) => {
    signIn({ role })
    routeGet({ '/workshops/': page([]), '/workshop-invitations/': page([]) })
    renderApp(<Workshops />)
    expect(await screen.findByText(/needs a Workshop account/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /New workshop/ })).not.toBeInTheDocument()
  })

  it('accepts and declines invitations through the members endpoint', async () => {
    routeGet({ '/workshops/': page([]), '/workshop-invitations/': page([invitation()]) })
    vi.mocked(api.patch).mockResolvedValue({ data: {} } as never)
    renderApp(<Workshops />)
    expect(await screen.findByText('Beta Workshop')).toBeInTheDocument(); expect(screen.getByText(/Invited by Boss Person/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Accept' }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/workshops/5/members/9/', { status: 'active' }))
    fireEvent.click(screen.getByRole('button', { name: 'Decline' }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/workshops/5/members/9/', { status: 'removed' }))
  })

  it('creating a workshop posts the form and opens it', async () => {
    signIn({ role: 'workshop' })
    routeGet({ '/workshops/': page([]), '/workshop-invitations/': page([]) })
    vi.mocked(api.post).mockResolvedValue({ data: { id: 42 } } as never)
    renderApp(<Workshops />, { path: '/app/workshops', url: '/app/workshops' })
    fireEvent.click((await screen.findAllByRole('button', { name: /New workshop/ }))[0])
    const create = await screen.findByRole('button', { name: 'Create' }); expect(create).toBeDisabled()          // needs a name
    fireEvent.change(screen.getByLabelText('Workshop name'), { target: { value: 'Samarkand Furniture' } })
    fireEvent.change(screen.getByLabelText('Phone'), { target: { value: '+998901112233' } })
    fireEvent.click(create)
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/workshops/', expect.objectContaining({ name: 'Samarkand Furniture', phone: '+998901112233' })))
    expect(await screen.findByTestId('elsewhere')).toBeInTheDocument()   // navigated to /app/workshops/42
  })

  it('shows the server message when creation is refused', async () => {
    signIn({ role: 'workshop' })
    routeGet({ '/workshops/': page([]), '/workshop-invitations/': page([]) })
    vi.mocked(api.post).mockRejectedValue(httpError(400, { error: { status: 400, detail: 'Validation failed.', fields: { name: ['Enter at least 2 characters.'] } } }))
    renderApp(<Workshops />)
    fireEvent.click((await screen.findAllByRole('button', { name: /New workshop/ }))[0])
    fireEvent.change(await screen.findByLabelText('Workshop name'), { target: { value: 'ab' } }); fireEvent.click(screen.getByRole('button', { name: 'Create' }))
    expect(await screen.findByText('Enter at least 2 characters.')).toBeInTheDocument()
  })
})
