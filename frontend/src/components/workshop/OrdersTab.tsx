import { useState } from 'react'
import { ClipboardList, Pencil, Plus, Search, Trash2 } from 'lucide-react'
import { api, apiError } from '../../lib/api'
import { fmtDate, fmtDateTime, fmtMoney } from '../../lib/format'
import { useT } from '../../lib/i18n'
import { parseAmount, ORDER_STATUSES, PAYMENT_STATUSES } from '../../lib/workshop'
import type { Order, OrderStatus, Workshop } from '../../lib/types'
import { useAction, useMembers, useOrder, useOrders, useTasks } from '../../hooks/workshops'
import { useDebounced } from '../../hooks/queries'
import { Button } from '../ui/Button'
import { DateField, Input, Select, Switch, Textarea } from '../ui/Field'
import { ConfirmDialog, Modal } from '../ui/Modal'
import { type Column, DataTable, EmptyState, ErrorState, Pagination, Skeleton } from '../ui/Misc'
import { OrderBadge, PayBadge, TaskBadge } from './common'
import { TaskModal } from './TasksTab'

const TERMINAL: OrderStatus[] = ['delivered', 'cancelled']
const PAGE = 20
interface Props { ws: Workshop; owner: boolean; writable: boolean }

type Form = { title: string; customer_name: string; customer_phone: string; customer_email: string; customer_address: string; description: string
  total_price: string; paid_amount: string; assigned_employee: string; start_date: string; deadline: string }
const blank = (): Form => ({ title: '', customer_name: '', customer_phone: '', customer_email: '', customer_address: '', description: '', total_price: '0', paid_amount: '0', assigned_employee: '', start_date: '', deadline: '' })
const fromOrder = (o: Order): Form => ({ title: o.title, customer_name: o.customer_name, customer_phone: o.customer_phone, customer_email: o.customer_email, customer_address: o.customer_address,
  description: o.description, total_price: o.total_price ?? '0', paid_amount: o.paid_amount ?? '0', assigned_employee: o.assigned_employee ? String(o.assigned_employee) : '', start_date: o.start_date ?? '', deadline: o.deadline ?? '' })

export function OrderFormModal({ ws, order, onClose }: { ws: Workshop; order?: Order; onClose: (saved?: Order) => void }) {
  const t = useT(); const members = useMembers(ws.id, { status: 'active' })
  const [f, setF] = useState<Form>(() => (order ? fromOrder(order) : blank())); const [errs, setErrs] = useState<Record<string, string>>({})
  const save = useAction(async (body: Record<string, unknown>) => (order ? (await api.patch<Order>(`/orders/${order.id}/`, body)).data : (await api.post<Order>('/orders/', { workshop: ws.id, ...body })).data),
    { ok: order ? t('ord.saved') : t('ord.created'), onSuccess: (o) => onClose(o), onError: (e) => setErrs({ ...apiError(e).fields, _: apiError(e).message }) })
  const set = (k: keyof Form) => (v: string) => setF((p) => ({ ...p, [k]: v }))
  const submit = () => {
    setErrs({})
    const money = (k: 'total_price' | 'paid_amount') => parseAmount(f[k])
    if (money('total_price') === null || money('paid_amount') === null) { setErrs({ total_price: money('total_price') === null ? t('f.numberRequired') : '', paid_amount: money('paid_amount') === null ? t('f.numberRequired') : '' }); return }
    const next: Record<string, unknown> = { ...f, total_price: money('total_price'), paid_amount: money('paid_amount'), assigned_employee: f.assigned_employee ? Number(f.assigned_employee) : null,
      start_date: f.start_date || null, deadline: f.deadline || null }
    if (order) { const prev = fromOrder(order); const same = (k: keyof Form) => (k === 'total_price' || k === 'paid_amount' ? Number(prev[k]) === next[k] : k === 'assigned_employee' ? (order.assigned_employee ?? null) === next[k] : (prev[k] || null) === (next[k] || null) || prev[k] === next[k])
      for (const k of Object.keys(prev) as (keyof Form)[]) if (same(k)) delete next[k] }
    if (order && !Object.keys(next).length) { onClose(); return }
    save.mutate(next)
  }
  const canPay = !order || !!order.total_price // employees never edit, owners get money fields
  return (
    <Modal open onClose={() => onClose()} title={order ? t('ord.edit') : t('ord.new')} wide
      footer={<><Button variant="ghost" onClick={() => onClose()}>{t('common.cancel')}</Button><Button loading={save.isPending} disabled={!f.title.trim() || !f.customer_name.trim()} onClick={submit}>{t('common.save')}</Button></>}>
      <form className="grid gap-4 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); submit() }}>
        <div className="sm:col-span-2"><Input label={t('ord.title')} value={f.title} maxLength={200} onChange={(e) => set('title')(e.target.value)} error={errs.title} autoFocus /></div>
        <Input label={t('ord.customer')} value={f.customer_name} maxLength={160} onChange={(e) => set('customer_name')(e.target.value)} error={errs.customer_name} />
        <Input label={t('ws.phone')} value={f.customer_phone} maxLength={32} onChange={(e) => set('customer_phone')(e.target.value)} error={errs.customer_phone} />
        <Input label={t('ws.email')} type="email" value={f.customer_email} onChange={(e) => set('customer_email')(e.target.value)} error={errs.customer_email} />
        <Input label={t('ws.address')} value={f.customer_address} maxLength={255} onChange={(e) => set('customer_address')(e.target.value)} error={errs.customer_address} />
        <div className="sm:col-span-2"><Textarea label={t('ws.description')} value={f.description} onChange={(e) => set('description')(e.target.value)} error={errs.description} /></div>
        {canPay && <>
          <Input label={t('ord.total')} inputMode="decimal" value={f.total_price} onChange={(e) => set('total_price')(e.target.value)} error={errs.total_price} />
          <Input label={t('ord.paid')} inputMode="decimal" value={f.paid_amount} onChange={(e) => set('paid_amount')(e.target.value)} error={errs.paid_amount} hint={t('ord.paidHint')} /></>}
        <DateField label={t('ord.start')} value={f.start_date} onChange={set('start_date')} error={errs.start_date} />
        <DateField label={t('ord.deadline')} value={f.deadline} onChange={set('deadline')} error={errs.deadline} />
        <div className="sm:col-span-2"><Select label={t('ord.assignee')} value={f.assigned_employee} onChange={(e) => set('assigned_employee')(e.target.value)} error={errs.assigned_employee}
          options={[{ value: '', label: t('common.none') }, ...(members.data?.results ?? []).map((m) => ({ value: m.id, label: m.user.full_name }))]} /></div>
        {errs._ && !Object.keys(errs).some((k) => k !== '_' && errs[k]) && <p role="alert" className="text-sm text-danger sm:col-span-2">{errs._}</p>}
      </form>
    </Modal>
  )
}

export function OrderModal({ id, ws, owner, writable, onClose, onEdit }: { id: number; ws: Workshop; owner: boolean; writable: boolean; onClose: () => void; onEdit: (o: Order) => void }) {
  const t = useT(); const q = useOrder(id); const tasks = useTasks({ order: id, page_size: 50 })
  const [note, setNote] = useState(''); const [paidDraft, setPaidDraft] = useState<string | null>(null); const [confirm, setConfirm] = useState<'cancel' | 'delete' | 'refund' | null>(null); const [task, setTask] = useState<number | 'new' | null>(null)
  const o = q.data
  const paid = paidDraft ?? o?.paid_amount ?? ''   // what the user typed, else the saved amount
  const patch = useAction((body: Record<string, unknown>) => api.patch<Order>(`/orders/${id}/`, body), { ok: t('ord.saved'), onSuccess: () => setPaidDraft(null) })
  const remove = useAction(() => api.delete(`/orders/${id}/`), { ok: t('ord.deleted'), onSuccess: onClose })
  const move = (s: OrderStatus) => { if (s === 'cancelled') setConfirm('cancel'); else patch.mutate({ status: s, ...(note.trim() ? { status_note: note.trim() } : {}) }, { onSuccess: () => setNote('') }) }
  if (!o) return <Modal open onClose={onClose} title={t('common.loading')}>{q.isError ? <ErrorState message={apiError(q.error).message} onRetry={() => q.refetch()} /> : <Skeleton className="h-48" />}</Modal>
  const final = TERMINAL.includes(o.status)
  const showMoney = o.total_price !== undefined
  return (
    <Modal open onClose={onClose} wide title={`${o.order_number} · ${o.title}`}
      footer={<>{owner && writable && <Button variant="danger" icon={<Trash2 size={15} />} onClick={() => setConfirm('delete')}>{t('common.delete')}</Button>}<div className="flex-1" />
        {owner && writable && !final && <Button variant="secondary" icon={<Pencil size={15} />} onClick={() => onEdit(o)}>{t('common.edit')}</Button>}<Button variant="ghost" onClick={onClose}>{t('common.close')}</Button></>}>
      <div className="space-y-5">
        <div className="flex flex-wrap items-center gap-2"><OrderBadge s={o.status} />{o.payment_status && <PayBadge s={o.payment_status} />}
          {o.deadline && <span className="text-xs text-muted">{t('ord.deadline')}: <span className="num">{fmtDate(o.deadline)}</span></span>}</div>
        <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
          {([[t('ord.customer'), o.customer_name], [t('ws.phone'), o.customer_phone], [t('ws.email'), o.customer_email], [t('ws.address'), o.customer_address], [t('ord.assignee'), o.assigned_employee_detail?.full_name],
            [t('ord.start'), o.start_date ? fmtDate(o.start_date) : ''], [t('ord.completedAt'), o.completed_at ? fmtDateTime(o.completed_at) : ''], [t('ord.project'), o.project?.name]] as [string, string | undefined][])
            .filter(([, v]) => v).map(([k, v]) => <div key={k} className="flex justify-between gap-3 border-b border-line/50 py-1"><dt className="text-muted">{k}</dt><dd className="text-right">{v}</dd></div>)}
        </dl>
        {o.description && <p className="whitespace-pre-wrap rounded-lg bg-card2/60 p-3 text-sm">{o.description}</p>}

        {showMoney && (<section aria-label={t('ord.money')} className="rounded-lg border border-line p-4">
          <div className="grid grid-cols-3 gap-3 text-center">{[[t('ord.total'), o.total_price], [t('ord.paid'), o.paid_amount], [t('ord.outstanding'), o.outstanding_amount]].map(([k, v]) => <div key={k}><p className="text-xs text-muted">{k}</p><p className="num text-lg font-semibold">{fmtMoney(v)}</p></div>)}</div>
          {owner && writable && o.payment_status !== 'refunded' && (<div className="mt-4 flex flex-wrap items-end gap-2">
            <div className="w-40"><Input label={t('ord.paid')} inputMode="decimal" value={paid} onChange={(e) => setPaidDraft(e.target.value)} /></div>
            <Button size="sm" variant="secondary" loading={patch.isPending} disabled={parseAmount(paid) === null || parseAmount(paid) === Number(o.paid_amount)} onClick={() => patch.mutate({ paid_amount: parseAmount(paid) })}>{t('ord.recordPayment')}</Button>
            {Number(o.paid_amount) > 0 && <Button size="sm" variant="ghost" onClick={() => setConfirm('refund')}>{t('ord.refund')}</Button>}</div>)}
          {o.payment_status === 'refunded' && <p className="mt-3 text-xs text-muted">{t('ord.refundedNote')}</p>}
        </section>)}

        {!!o.allowed_next_statuses.length && writable && (<section aria-label={t('ord.moveTo')} className="space-y-3 rounded-lg border border-line p-4">
          <h3 className="text-sm font-semibold">{t('ord.moveTo')}</h3>
          <Input label={t('ord.note')} value={note} maxLength={255} onChange={(e) => setNote(e.target.value)} />
          <div className="flex flex-wrap gap-2">{o.allowed_next_statuses.map((s) => (
            <Button key={s} size="sm" variant={s === 'cancelled' ? 'danger' : 'secondary'} loading={patch.isPending && patch.variables?.status === s} onClick={() => move(s)}>{t(`order.st.${s}`)}</Button>))}</div>
        </section>)}

        <section aria-label={t('task.title')}>
          <div className="mb-2 flex items-center justify-between"><h3 className="text-sm font-semibold">{t('task.title')} <span className="num text-muted">({tasks.data?.count ?? 0})</span></h3>
            {owner && writable && !final && <Button size="sm" variant="ghost" icon={<Plus size={14} />} onClick={() => setTask('new')}>{t('task.new')}</Button>}</div>
          {tasks.isLoading ? <Skeleton className="h-12" /> : tasks.data?.results.length ? (
            <ul className="divide-y divide-line/60 rounded-lg border border-line">{tasks.data.results.map((x) => (
              <li key={x.id}><button onClick={() => setTask(x.id)} className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-card2/60"><span className="truncate">{x.title}</span>
                <span className="flex shrink-0 items-center gap-2 text-xs text-muted">{x.assigned_to_detail?.full_name}<TaskBadge s={x.status} /></span></button></li>))}</ul>)
            : <p className="text-sm text-muted">{t('task.noneForOrder')}</p>}
        </section>

        {!!o.status_history?.length && (<section aria-label={t('ord.history')}><h3 className="mb-2 text-sm font-semibold">{t('ord.history')}</h3>
          <ol className="space-y-2 border-l border-line pl-4">{o.status_history.map((h) => (
            <li key={h.id} className="relative text-sm"><span className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-primary" aria-hidden />
              <p>{h.from_status ? <>{t(`order.st.${h.from_status}`)} → <b>{t(`order.st.${h.to_status}`)}</b></> : <b>{t(`order.st.${h.to_status}`)}</b>}</p>
              <p className="text-xs text-muted">{fmtDateTime(h.created_at)} · {h.changed_by?.full_name ?? '-'}{h.note ? ` · ${h.note}` : ''}</p></li>))}</ol></section>)}
      </div>
      <ConfirmDialog cancelLabel={t('common.cancel')} open={confirm === 'cancel'} onClose={() => setConfirm(null)} title={t('ord.cancelTitle')} message={t('ord.cancelMsg')} confirmLabel={t('ord.cancelDo')} loading={patch.isPending}
        onConfirm={() => patch.mutate({ status: 'cancelled', ...(note.trim() ? { status_note: note.trim() } : {}) }, { onSuccess: () => { setConfirm(null); setNote('') }, onSettled: () => setConfirm(null) })} />
      <ConfirmDialog cancelLabel={t('common.cancel')} open={confirm === 'delete'} onClose={() => setConfirm(null)} title={t('ord.deleteTitle')} message={t('ord.deleteMsg')} loading={remove.isPending} onConfirm={() => remove.mutate(undefined, { onSettled: () => setConfirm(null) })} />
      <ConfirmDialog cancelLabel={t('common.cancel')} open={confirm === 'refund'} onClose={() => setConfirm(null)} title={t('ord.refundTitle')} message={t('ord.refundMsg')} confirmLabel={t('ord.refund')} loading={patch.isPending}
        onConfirm={() => patch.mutate({ payment_status: 'refunded' }, { onSettled: () => setConfirm(null) })} />
      {task !== null && <TaskModal ws={ws} owner={owner} writable={writable} taskId={task === 'new' ? null : task} orderId={o.id} onClose={() => setTask(null)} />}
    </Modal>
  )
}

export function OrdersTab({ ws, owner, writable }: Props) {
  const t = useT()
  const [page, setPage] = useState(1); const [search, setSearch] = useState(''); const [status, setStatus] = useState(''); const [pay, setPay] = useState(''); const [overdue, setOverdue] = useState(false); const [mine, setMine] = useState(false)
  const [form, setForm] = useState<Order | 'new' | null>(null); const [open, setOpen] = useState<number | null>(null)
  const dq = useDebounced(search, 300)
  const reset = <T,>(set: (v: T) => void) => (v: T) => { set(v); setPage(1) }   // any filter change goes back to the first page
  const list = useOrders({ workshop: ws.id, page, page_size: PAGE, search: dq, status, payment_status: owner ? pay : '', overdue, mine })
  const cols: Column<Order>[] = [
    { key: 'n', header: t('ord.number'), className: 'num hidden whitespace-nowrap sm:table-cell', render: (o) => o.order_number },
    { key: 't', header: t('ord.title'), render: (o) => <div className="min-w-0"><p className="num text-xs text-muted sm:hidden">{o.order_number}</p><p className="truncate font-medium">{o.title}</p><p className="truncate text-xs text-muted">{o.customer_name}</p>
      <div className="mt-1 flex flex-wrap gap-1 sm:hidden"><OrderBadge s={o.status} />{o.payment_status && <PayBadge s={o.payment_status} />}</div></div> },
    { key: 's', header: t('ord.status'), className: 'hidden sm:table-cell', render: (o) => <OrderBadge s={o.status} /> },
    { key: 'd', header: t('ord.deadline'), className: 'num hidden whitespace-nowrap md:table-cell', render: (o) => (o.deadline ? fmtDate(o.deadline) : '-') },
    ...(owner ? [
      { key: 'p', header: t('ord.payment'), className: 'hidden sm:table-cell', render: (o: Order) => (o.payment_status ? <PayBadge s={o.payment_status} /> : null) },
      { key: 'a', header: t('ord.total'), className: 'num hidden text-right lg:table-cell', render: (o: Order) => fmtMoney(o.total_price) }] : []),
  ]
  const filtered = !!(dq || status || pay || overdue || mine)
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="relative min-w-52 flex-1"><Input label={t('common.search')} value={search} onChange={(e) => reset(setSearch)(e.target.value)} suffix={<Search size={15} />} /></div>
        <div className="w-40"><Select label={t('ord.status')} value={status} onChange={(e) => reset(setStatus)(e.target.value)} options={[{ value: '', label: t('common.all') }, ...ORDER_STATUSES.map((s) => ({ value: s, label: t(`order.st.${s}`) }))]} /></div>
        {owner && <div className="w-40"><Select label={t('ord.payment')} value={pay} onChange={(e) => reset(setPay)(e.target.value)} options={[{ value: '', label: t('common.all') }, ...PAYMENT_STATUSES.map((s) => ({ value: s, label: t(`pay.${s}`) }))]} /></div>}
        <label className="flex items-center gap-2 pb-2 text-sm"><Switch checked={overdue} onChange={reset(setOverdue)} label={t('ord.overdue')} />{t('ord.overdue')}</label>
        {!owner && <label className="flex items-center gap-2 pb-2 text-sm"><Switch checked={mine} onChange={reset(setMine)} label={t('common.mine')} />{t('common.mine')}</label>}
        {owner && writable && <Button icon={<Plus size={16} />} onClick={() => setForm('new')}>{t('ord.new')}</Button>}
      </div>
      {list.isLoading ? <Skeleton className="h-64" /> : list.isError ? <ErrorState message={apiError(list.error).message} onRetry={() => list.refetch()} />
        : <DataTable compact columns={cols} rows={list.data?.results ?? []} onRowClick={(o) => setOpen(o.id)}
          empty={<EmptyState icon={<ClipboardList size={22} />} title={filtered ? t('ord.noMatch') : t('ord.empty')} text={filtered ? undefined : owner ? t('ord.emptyOwner') : t('ord.emptyEmployee')}
            action={!filtered && owner && writable ? <Button icon={<Plus size={16} />} onClick={() => setForm('new')}>{t('ord.new')}</Button> : undefined} />} />}
      {list.data && <Pagination page={page} count={list.data.count} pageSize={PAGE} onPage={setPage} />}
      {form && <OrderFormModal ws={ws} order={form === 'new' ? undefined : form} onClose={(saved) => { setForm(null); if (saved && form !== 'new') setOpen(saved.id) }} />}
      {open !== null && !form && <OrderModal id={open} ws={ws} owner={owner} writable={writable} onClose={() => setOpen(null)} onEdit={(o) => setForm(o)} />}
    </div>
  )
}
