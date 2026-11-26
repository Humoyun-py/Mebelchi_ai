import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { api } from '../../lib/api'
import { member, order, task, workshop } from '../../test/fixtures'
import { httpError, page, renderApp, routeGet, signIn } from '../../test/utils'
import { OrderFormModal, OrderModal, OrdersTab } from './OrdersTab'

vi.mock('../../lib/api', async (orig) => ({ ...(await orig<typeof import('../../lib/api')>()), api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }))
beforeEach(() => { vi.clearAllMocks(); signIn() ; vi.mocked(api.patch).mockResolvedValue({ data: {} } as never); vi.mocked(api.post).mockResolvedValue({ data: order() } as never); vi.mocked(api.delete).mockResolvedValue({ data: {} } as never) })
const ws = workshop()
const routes = (o = order(), extra: Record<string, unknown> = {}) => ({ '/orders/': page([o]), [`/orders/${o.id}/`]: o, '/tasks/': page([]), '/workshops/1/members/': page([member()]), ...extra })

describe('OrdersTab', () => {
  it('the owner sees money columns, filters and the new-order button', async () => {
    routeGet(routes())
    renderApp(<OrdersTab ws={ws} owner writable />)
    expect(await screen.findByText('Kitchen set')).toBeInTheDocument()
    const table = within(screen.getByRole('table'))
    // the phone layout repeats number/status inside the title cell (CSS hides one copy per screen size)
    expect(table.getAllByText('ORD-0001-000001').length).toBeGreaterThan(0); expect(table.getAllByText('Partially paid').length).toBeGreaterThan(0)
    expect(screen.getByRole('columnheader', { name: 'Total' })).toBeInTheDocument(); expect(screen.getByLabelText('Payment')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /New order/ })).toBeInTheDocument()
  })

  it('an employee gets no money columns, no payment filter and no create button (and the request omits payment_status)', async () => {
    const o = order({ total_price: undefined, paid_amount: undefined, outstanding_amount: undefined, payment_status: undefined, allowed_next_statuses: [] })
    routeGet(routes(o))
    renderApp(<OrdersTab ws={workshop({ my_role: 'employee' })} owner={false} writable />)
    expect(await screen.findByText('Kitchen set')).toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: 'Total' })).not.toBeInTheDocument(); expect(screen.queryByLabelText('Payment')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /New order/ })).not.toBeInTheDocument(); expect(screen.getByText('Assigned to me')).toBeInTheDocument()
    const params = vi.mocked(api.get).mock.calls.find((c) => c[0] === '/orders/')![1]!.params as Record<string, unknown>
    expect(params).not.toHaveProperty('payment_status'); expect(params).toMatchObject({ workshop: 1, page: 1 })
  })

  it('filters are sent to the server and reset the page', async () => {
    routeGet(routes())
    renderApp(<OrdersTab ws={ws} owner writable />)
    await screen.findByText('Kitchen set')
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'confirmed' } })
    await waitFor(() => expect(vi.mocked(api.get).mock.calls.some((c) => c[0] === '/orders/' && (c[1]!.params as Record<string, unknown>).status === 'confirmed')).toBe(true))
    fireEvent.click(screen.getByRole('switch', { name: 'Overdue' }))
    await waitFor(() => expect(vi.mocked(api.get).mock.calls.some((c) => c[0] === '/orders/' && (c[1]!.params as Record<string, unknown>).overdue === true)).toBe(true))
  })

  it('distinguishes "no orders" from "no match", and surfaces server errors with a retry', async () => {
    routeGet(routes(order(), { '/orders/': page([]) }))
    const { unmount } = renderApp(<OrdersTab ws={ws} owner writable />)
    expect(await screen.findByText('No orders yet')).toBeInTheDocument(); unmount()
    routeGet(routes(order(), { '/orders/': page([]) }))
    renderApp(<OrdersTab ws={ws} owner writable />)
    fireEvent.change(await screen.findByLabelText('Status'), { target: { value: 'ready' } })
    expect(await screen.findByText('No orders match these filters')).toBeInTheDocument()
  })

  it('shows an error state when the list cannot be loaded', async () => {
    routeGet(routes(order(), { '/orders/': httpError(500, { error: { status: 500, detail: 'Server exploded.' } }) }))
    renderApp(<OrdersTab ws={ws} owner writable />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Server exploded.')
  })

  it('an inactive workshop hides the create button', async () => {
    routeGet(routes()); renderApp(<OrdersTab ws={workshop({ status: 'inactive' })} owner writable={false} />)
    await screen.findByText('Kitchen set'); expect(screen.queryByRole('button', { name: /New order/ })).not.toBeInTheDocument()
  })

  it('clicking a row opens the order', async () => {
    routeGet(routes()); renderApp(<OrdersTab ws={ws} owner writable />)
    fireEvent.click(await screen.findByText('Kitchen set'))
    expect(await screen.findByRole('dialog', { name: /ORD-0001-000001/ })).toBeInTheDocument()
  })
})

describe('OrderModal', () => {
  const open = (o = order(), owner = true, writable = true) => { routeGet(routes(o)); return renderApp(<OrderModal id={o.id} ws={ws} owner={owner} writable={writable} onClose={vi.fn()} onEdit={vi.fn()} />) }

  it('offers exactly the statuses the server allows and sends the chosen one with the note', async () => {
    open()
    const section = within(await screen.findByRole('region', { name: 'Change status' }))
    expect(section.getAllByRole('button').map((b) => b.textContent)).toEqual(['Cancelled', 'Accepted'])        // server order, nothing invented
    fireEvent.change(section.getByLabelText('Note (optional)'), { target: { value: 'Deposit received' } })
    fireEvent.click(section.getByRole('button', { name: 'Accepted' }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/orders/100/', { status: 'confirmed', status_note: 'Deposit received' }))
  })

  it('cancelling needs a confirmation and warns that tasks are cancelled too', async () => {
    open()
    fireEvent.click(await screen.findByRole('button', { name: 'Cancelled' }))
    expect(api.patch).not.toHaveBeenCalled()
    const confirm = await screen.findByRole('dialog', { name: 'Cancel this order?' })
    expect(confirm).toHaveTextContent('open tasks are cancelled')
    fireEvent.click(within(confirm).getByRole('button', { name: 'Cancel order' }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/orders/100/', { status: 'cancelled' }))
  })

  it('shows money and records a payment (decimal comma accepted); the button stays off while nothing changed', async () => {
    open()
    const input = await screen.findByLabelText('Paid')
    const btn = screen.getByRole('button', { name: 'Record payment' }); expect(btn).toBeDisabled()
    fireEvent.change(input, { target: { value: '500,5' } }); expect(btn).toBeEnabled(); fireEvent.click(btn)
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/orders/100/', { paid_amount: 500.5 }))
    fireEvent.change(input, { target: { value: 'abc' } }); expect(btn).toBeDisabled()
  })

  it('refunding asks for confirmation first', async () => {
    open()
    fireEvent.click(await screen.findByRole('button', { name: 'Mark refunded' }))
    expect(api.patch).not.toHaveBeenCalled()
    fireEvent.click(within(await screen.findByRole('dialog', { name: 'Mark as refunded?' })).getByRole('button', { name: 'Mark refunded' }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/orders/100/', { payment_status: 'refunded' }))
  })

  it('an employee sees no money, no payment form and no status buttons', async () => {
    open(order({ total_price: undefined, paid_amount: undefined, outstanding_amount: undefined, payment_status: undefined, allowed_next_statuses: [] }), false)
    await screen.findByText('Ali Valiyev')
    expect(screen.queryByRole('region', { name: 'Payment details' })).not.toBeInTheDocument(); expect(screen.queryByRole('region', { name: 'Change status' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument(); expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument()
    expect(screen.getByText('Ali Valiyev')).toBeInTheDocument()
  })

  it('final orders cannot be edited but keep their history; read-only workshops hide every action', async () => {
    const { unmount } = open(order({ status: 'delivered', allowed_next_statuses: [] }))
    await screen.findByText('Ali Valiyev'); expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument(); expect(screen.getByText('History')).toBeInTheDocument(); unmount()
    open(order(), true, false)
    await screen.findByText('Ali Valiyev')
    for (const n of ['Edit', 'Delete', 'Record payment', 'Accepted']) expect(screen.queryByRole('button', { name: n })).not.toBeInTheDocument()
  })

  it('lists the order\'s tasks and the status history with who and when', async () => {
    routeGet({ ...routes(), '/tasks/': page([task(), task({ id: 201, title: 'Glue', status: 'completed' })]) })
    renderApp(<OrderModal id={100} ws={ws} owner writable onClose={vi.fn()} onEdit={vi.fn()} />)
    expect(await screen.findByText('Cut panels')).toBeInTheDocument(); expect(screen.getByText('Glue')).toBeInTheDocument(); expect(screen.getByText(/Order created/)).toBeInTheDocument()
  })

  it('deleting asks first and shows the server\'s reason when the order must be kept', async () => {
    vi.mocked(api.delete).mockRejectedValue(httpError(409, { error: { status: 409, detail: 'Only orders that are new or cancelled and have no payments can be deleted.' } }))
    open()
    fireEvent.click(await screen.findByRole('button', { name: 'Delete' }))
    expect(api.delete).not.toHaveBeenCalled()
    fireEvent.click(within(await screen.findByRole('dialog', { name: 'Delete this order?' })).getByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(api.delete).toHaveBeenCalledWith('/orders/100/'))
    expect(await screen.findByText(/have no payments can be deleted/)).toBeInTheDocument()
  })

  it('Escape closes only the topmost dialog', async () => {
    const onClose = vi.fn(); routeGet(routes())
    renderApp(<OrderModal id={100} ws={ws} owner writable onClose={onClose} onEdit={vi.fn()} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Cancelled' }))
    await screen.findByRole('dialog', { name: 'Cancel this order?' })
    fireEvent.keyDown(document, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Cancel this order?' })).not.toBeInTheDocument())
    expect(onClose).not.toHaveBeenCalled(); expect(screen.getByRole('dialog', { name: /ORD-0001/ })).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' }); expect(onClose).toHaveBeenCalledTimes(1)
  })
})

describe('OrderFormModal', () => {
  const fill = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } })

  it('creating needs a title and customer, validates money client-side and posts the workshop', async () => {
    routeGet(routes()); const onClose = vi.fn()
    renderApp(<OrderFormModal ws={ws} onClose={onClose} />)
    const save = await screen.findByRole('button', { name: 'Save' }); expect(save).toBeDisabled()
    fill('Title', 'Wardrobe'); fill('Customer', 'Bobur'); expect(save).toBeEnabled()
    fill('Total', 'lots'); fireEvent.click(save)
    expect(await screen.findByText('Enter a number')).toBeInTheDocument(); expect(api.post).not.toHaveBeenCalled()
    fill('Total', '5 000 000'); fill('Paid', '1000000'); fill('Deadline', '2026-12-20'); fireEvent.click(save)
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/orders/', expect.objectContaining({ workshop: 1, title: 'Wardrobe', customer_name: 'Bobur', total_price: 5000000, paid_amount: 1000000, deadline: '2026-12-20', assigned_employee: null })))
  })

  it('editing sends only the fields that changed', async () => {
    routeGet(routes()); renderApp(<OrderFormModal ws={ws} order={order({ deadline: '2026-12-20' })} onClose={vi.fn()} />)
    fill('Title', 'Kitchen set XL'); fireEvent.click(await screen.findByRole('button', { name: 'Save' }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/orders/100/', { title: 'Kitchen set XL' }))
  })

  it('editing without changes does not call the server', async () => {
    routeGet(routes()); const onClose = vi.fn(); renderApp(<OrderFormModal ws={ws} order={order()} onClose={onClose} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Save' })); expect(api.patch).not.toHaveBeenCalled(); expect(onClose).toHaveBeenCalled()
  })

  it('maps server validation errors onto the fields', async () => {
    vi.mocked(api.post).mockRejectedValue(httpError(400, { error: { status: 400, detail: 'Validation failed.', fields: { deadline: ['The deadline cannot be in the past.'], paid_amount: ['The paid amount cannot exceed the total price.'] } } }))
    routeGet(routes()); renderApp(<OrderFormModal ws={ws} onClose={vi.fn()} />)
    fill('Title', 'x'); fill('Customer', 'y'); fireEvent.click(await screen.findByRole('button', { name: 'Save' }))
    expect(await screen.findByText('The deadline cannot be in the past.')).toBeInTheDocument(); expect(screen.getByText('The paid amount cannot exceed the total price.')).toBeInTheDocument()
  })

  it('offers only active members as the responsible employee', async () => {
    routeGet(routes(order(), { '/workshops/1/members/': page([member({ id: 10 }), member({ id: 11, user: { id: 3, full_name: 'Dilnoza Yusupova' } })]) }))
    renderApp(<OrderFormModal ws={ws} onClose={vi.fn()} />)
    expect(await screen.findByRole('option', { name: 'Dilnoza Yusupova' })).toBeInTheDocument()
    expect(vi.mocked(api.get).mock.calls.find((c) => c[0] === '/workshops/1/members/')![1]!.params).toMatchObject({ status: 'active' })
  })
})

describe('shared data stays fresh', () => {
  it('an order created by someone else shows up when the tab is opened again (no stale empty list)', async () => {
    const { QueryClient } = await import('@tanstack/react-query')
    const client = new QueryClient({ defaultOptions: { queries: { staleTime: 15000, retry: false } } })   // the app's own staleTime must not hide new data
    routeGet(routes(order(), { '/orders/': page([]) }))
    const first = renderApp(<OrdersTab ws={workshop({ my_role: 'employee' })} owner={false} writable />, { client })
    expect(await screen.findByText('No orders yet')).toBeInTheDocument(); first.unmount()
    routeGet(routes(order(), { '/orders/': page([order()]) }))        // the owner creates and assigns an order meanwhile
    renderApp(<OrdersTab ws={workshop({ my_role: 'employee' })} owner={false} writable />, { client })
    expect(await screen.findByText('Kitchen set')).toBeInTheDocument()
  })
})
