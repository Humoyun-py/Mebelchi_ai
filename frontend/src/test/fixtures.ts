import type { Invitation, Member, Order, Task, Workshop } from '../lib/types'

export const person = (id: number, name: string, email?: string) => ({ id, full_name: name, ...(email ? { email } : {}) })
export const workshop = (o: Partial<Workshop> = {}): Workshop => ({ id: 1, name: 'Alpha Workshop', slug: 'alpha-workshop', description: '', owner: person(1, 'Me User'), phone: '', email: '', address: '',
  logo_url: null, status: 'active', my_role: 'owner', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', ...o })
export const member = (o: Partial<Member> = {}): Member => ({ id: 10, workshop: 1, user: person(2, 'Aziz Karimov', 'aziz@x.com'), role: 'employee', status: 'active', joined_at: '2026-02-01T00:00:00Z', removed_at: null, created_at: '2026-02-01T00:00:00Z', ...o })
export const invitation = (o: Partial<Invitation> = {}): Invitation => ({ id: 9, workshop: { id: 5, name: 'Beta Workshop' }, invited_by: person(7, 'Boss Person'), role: 'employee', status: 'invited', created_at: new Date().toISOString(), ...o })
export const order = (o: Partial<Order> = {}): Order => ({ id: 100, order_number: 'ORD-0001-000001', workshop: 1, customer_name: 'Ali Valiyev', customer_phone: '+998901234567', customer_email: '', customer_address: '',
  title: 'Kitchen set', description: '', related_project: null, project: null, total_price: '1000.00', paid_amount: '250.00', outstanding_amount: '750.00', payment_status: 'partially_paid', status: 'new',
  allowed_next_statuses: ['cancelled', 'confirmed'], assigned_employee: null, assigned_employee_detail: null, start_date: null, deadline: null, completed_at: null, created_at: '2026-03-01T00:00:00Z', updated_at: '2026-03-01T00:00:00Z',
  status_history: [{ id: 1, from_status: '', to_status: 'new', changed_by: person(1, 'Me User'), note: 'Order created', created_at: '2026-03-01T00:00:00Z' }], tasks_count: 0, ...o })
export const task = (o: Partial<Task> = {}): Task => ({ id: 200, workshop: 1, order: 100, order_number: 'ORD-0001-000001', title: 'Cut panels', description: '', assigned_to: 10, assigned_to_detail: { ...person(2, 'Aziz Karimov'), status: 'active' },
  priority: 'medium', status: 'pending', allowed_next_statuses: ['in_progress'], deadline: null, is_overdue: false, started_at: null, completed_at: null, created_at: '2026-03-01T00:00:00Z', status_history: [], ...o })
