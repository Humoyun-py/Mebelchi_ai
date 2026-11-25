import { useState } from 'react'
import { ListChecks, Plus, Search } from 'lucide-react'
import { api, apiError } from '../../lib/api'
import { fmtDateTime, fromLocalInput, toLocalInput } from '../../lib/format'
import { useT } from '../../lib/i18n'
import { TASK_PRIORITIES, TASK_STATUSES } from '../../lib/workshop'
import type { Task, TaskPriority, TaskStatus, Workshop } from '../../lib/types'
import { useAction, useMembers, useOrders, useTask, useTasks } from '../../hooks/workshops'
import { useDebounced } from '../../hooks/queries'
import { Button } from '../ui/Button'
import { DateField, Input, Select, Switch, Textarea } from '../ui/Field'
import { ConfirmDialog, Modal } from '../ui/Modal'
import { type Column, DataTable, EmptyState, ErrorState, Pagination, Skeleton } from '../ui/Misc'
import { PriorityBadge, TaskBadge } from './common'

const PAGE = 20
const FINAL: TaskStatus[] = ['completed', 'cancelled']
interface Props { ws: Workshop; owner: boolean; writable: boolean }

/** Create (taskId null), edit (owner) or just update the status of (assignee) a task. */
export function TaskModal({ ws, owner, writable, taskId, orderId, onClose }: Props & { taskId: number | null; orderId?: number; onClose: () => void }) {
  const t = useT(); const q = useTask(taskId); const members = useMembers(ws.id, { status: 'active' }); const orders = useOrders({ workshop: ws.id, page_size: 100 })
  const task = q.data
  const initial = task ? { title: task.title, description: task.description, order: task.order ? String(task.order) : '', assigned_to: task.assigned_to ? String(task.assigned_to) : '', priority: task.priority, deadline: toLocalInput(task.deadline) }
    : { title: '', description: '', order: orderId ? String(orderId) : '', assigned_to: '', priority: 'medium' as TaskPriority, deadline: '' }
  const [draft, setDraft] = useState<Partial<typeof initial>>({}); const f = { ...initial, ...draft }   // what the user typed on top of the saved values
  const [errs, setErrs] = useState<Record<string, string>>({}); const [note, setNote] = useState(''); const [del, setDel] = useState(false)
  const onError = (e: unknown) => setErrs({ ...apiError(e).fields, _: apiError(e).message })
  const save = useAction((body: Record<string, unknown>) => (taskId ? api.patch<Task>(`/tasks/${taskId}/`, body) : api.post<Task>('/tasks/', body)), { ok: taskId ? t('task.saved') : t('task.created'), onSuccess: () => { if (!taskId) onClose() }, onError })
  const move = useAction((status: TaskStatus) => api.patch<Task>(`/tasks/${taskId}/`, { status, ...(note.trim() ? { status_note: note.trim() } : {}) }), { ok: t('task.saved'), onSuccess: () => setNote('') })
  const remove = useAction(() => api.delete(`/tasks/${taskId}/`), { ok: t('task.deleted'), onSuccess: onClose })
  const set = (k: keyof typeof f) => (v: string) => setDraft((p) => ({ ...p, [k]: v }))
  const editable = owner && writable && (!task || !FINAL.includes(task.status))
  const submit = () => {
    setErrs({})
    const body: Record<string, unknown> = { title: f.title.trim(), description: f.description, priority: f.priority, assigned_to: f.assigned_to ? Number(f.assigned_to) : null }
    if (!task || toLocalInput(task.deadline) !== f.deadline) body.deadline = fromLocalInput(f.deadline)   // an unchanged (possibly past) deadline is not re-validated by sending it
    if (!taskId) { body.workshop = ws.id; if (f.order) body.order = Number(f.order) }
    save.mutate(body)
  }
  if (taskId && !task) return <Modal open onClose={onClose} title={t('common.loading')}>{q.isError ? <ErrorState message={apiError(q.error).message} onRetry={() => q.refetch()} /> : <Skeleton className="h-40" />}</Modal>
  const openOrders = (orders.data?.results ?? []).filter((o) => !['delivered', 'cancelled'].includes(o.status))
  return (
    <Modal open onClose={onClose} wide title={task ? task.title : t('task.new')}
      footer={<>{owner && writable && task && !task.started_at && <Button variant="danger" onClick={() => setDel(true)}>{t('common.delete')}</Button>}<div className="flex-1" />
        <Button variant="ghost" onClick={onClose}>{t('common.close')}</Button>{editable && <Button loading={save.isPending} disabled={!f.title.trim()} onClick={submit}>{t('common.save')}</Button>}</>}>
      <div className="space-y-5">
        {task && <div className="flex flex-wrap items-center gap-2"><TaskBadge s={task.status} /><PriorityBadge p={task.priority} />{task.order_number && <span className="num text-xs text-muted">{task.order_number}</span>}
          {task.is_overdue && <span className="text-xs font-medium text-danger">{t('task.overdue')}</span>}</div>}
        {editable ? (
          <form className="grid gap-4 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); submit() }}>
            <div className="sm:col-span-2"><Input label={t('task.name')} value={f.title} maxLength={200} onChange={(e) => set('title')(e.target.value)} error={errs.title} autoFocus={!task} /></div>
            <div className="sm:col-span-2"><Textarea label={t('ws.description')} value={f.description} onChange={(e) => set('description')(e.target.value)} error={errs.description} /></div>
            {!taskId && <Select label={t('task.order')} value={f.order} onChange={(e) => set('order')(e.target.value)} error={errs.order || errs.workshop} disabled={!!orderId}
              options={[{ value: '', label: t('task.noOrder') }, ...openOrders.map((o) => ({ value: o.id, label: `${o.order_number} · ${o.title}` }))]} />}
            <Select label={t('task.assignee')} value={f.assigned_to} onChange={(e) => set('assigned_to')(e.target.value)} error={errs.assigned_to}
              options={[{ value: '', label: t('task.unassigned') }, ...(members.data?.results ?? []).map((m) => ({ value: m.id, label: m.user.full_name }))]} />
            <Select label={t('task.priority')} value={f.priority} onChange={(e) => set('priority')(e.target.value)} options={TASK_PRIORITIES.map((p) => ({ value: p, label: t(`task.pr.${p}`) }))} />
            <DateField time label={t('task.deadline')} value={f.deadline} onChange={set('deadline')} error={errs.deadline} />
            {errs._ && !Object.keys(errs).some((k) => k !== '_' && errs[k]) && <p role="alert" className="text-sm text-danger sm:col-span-2">{errs._}</p>}
          </form>
        ) : task && (
          <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
            {([[t('task.assignee'), task.assigned_to_detail?.full_name], [t('task.deadline'), task.deadline ? fmtDateTime(task.deadline) : ''], [t('task.started'), task.started_at ? fmtDateTime(task.started_at) : ''],
              [t('task.completedAt'), task.completed_at ? fmtDateTime(task.completed_at) : '']] as [string, string | undefined][]).filter(([, v]) => v)
              .map(([k, v]) => <div key={k} className="flex justify-between gap-3 border-b border-line/50 py-1"><dt className="text-muted">{k}</dt><dd className="text-right">{v}</dd></div>)}
            {task.description && <p className="whitespace-pre-wrap rounded-lg bg-card2/60 p-3 text-sm sm:col-span-2">{task.description}</p>}
          </dl>)}

        {task && !!task.allowed_next_statuses.length && writable && (<section aria-label={t('task.moveTo')} className="space-y-3 rounded-lg border border-line p-4">
          <h3 className="text-sm font-semibold">{t('task.moveTo')}</h3>
          <Input label={t('ord.note')} value={note} maxLength={255} onChange={(e) => setNote(e.target.value)} />
          <div className="flex flex-wrap gap-2">{task.allowed_next_statuses.map((s) => (
            <Button key={s} size="sm" variant={s === 'cancelled' ? 'danger' : 'secondary'} loading={move.isPending && move.variables === s} onClick={() => move.mutate(s)}>{t(`task.st.${s}`)}</Button>))}</div>
          {errs._ && <span hidden />}
        </section>)}

        {!!task?.status_history?.length && (<section aria-label={t('ord.history')}><h3 className="mb-2 text-sm font-semibold">{t('ord.history')}</h3>
          <ol className="space-y-2 border-l border-line pl-4">{task.status_history.map((h) => (
            <li key={h.id} className="relative text-sm"><span className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-primary" aria-hidden />
              <p>{h.from_status ? <>{t(`task.st.${h.from_status}`)} → <b>{t(`task.st.${h.to_status}`)}</b></> : <b>{t(`task.st.${h.to_status}`)}</b>}</p>
              <p className="text-xs text-muted">{fmtDateTime(h.created_at)} · {h.changed_by?.full_name ?? '-'}{h.note ? ` · ${h.note}` : ''}</p></li>))}</ol></section>)}
      </div>
      <ConfirmDialog cancelLabel={t('common.cancel')} open={del} onClose={() => setDel(false)} title={t('task.deleteTitle')} message={t('task.deleteMsg')} loading={remove.isPending} onConfirm={() => remove.mutate(undefined, { onSettled: () => setDel(false) })} />
    </Modal>
  )
}

export function TasksTab({ ws, owner, writable }: Props) {
  const t = useT()
  const [page, setPage] = useState(1); const [search, setSearch] = useState(''); const [status, setStatus] = useState(''); const [priority, setPriority] = useState(''); const [assignee, setAssignee] = useState('')
  const [overdue, setOverdue] = useState(false); const [mine, setMine] = useState(false); const [open, setOpen] = useState<number | 'new' | null>(null)
  const dq = useDebounced(search, 300); const members = useMembers(ws.id, { status: 'active' }, owner)
  const reset = <T,>(set: (v: T) => void) => (v: T) => { set(v); setPage(1) }   // any filter change goes back to the first page
  const list = useTasks({ workshop: ws.id, page, page_size: PAGE, search: dq, status, priority, assigned_to: owner ? assignee : '', overdue, mine })
  const quick = useAction(({ id, status }: { id: number; status: TaskStatus }) => api.patch<Task>(`/tasks/${id}/`, { status }), { ok: t('task.saved') })
  const cols: Column<Task>[] = [
    { key: 't', header: t('task.name'), render: (x) => <div className="min-w-0"><p className="truncate font-medium">{x.title}</p>{x.order_number && <p className="num truncate text-xs text-muted">{x.order_number}</p>}
      <div className="mt-1 flex flex-wrap items-center gap-1 sm:hidden"><TaskBadge s={x.status} /><span className="text-xs text-muted">{x.assigned_to_detail?.full_name}</span></div></div> },
    { key: 'a', header: t('task.assignee'), className: 'hidden sm:table-cell', render: (x) => x.assigned_to_detail?.full_name ?? <span className="text-muted">{t('task.unassigned')}</span> },
    { key: 'p', header: t('task.priority'), className: 'hidden md:table-cell', render: (x) => <PriorityBadge p={x.priority} /> },
    { key: 's', header: t('ord.status'), className: 'hidden sm:table-cell', render: (x) => <TaskBadge s={x.status} /> },
    { key: 'd', header: t('task.deadline'), className: 'num hidden whitespace-nowrap lg:table-cell', render: (x) => (x.deadline ? <span className={x.is_overdue ? 'text-danger' : ''}>{fmtDateTime(x.deadline)}</span> : '-') },
    { key: 'x', header: '', render: (x) => (writable && x.allowed_next_statuses.length
      ? <div className="flex flex-wrap justify-end gap-1">{x.allowed_next_statuses.filter((s) => s !== 'cancelled').slice(0, 2).map((s) => (
        <Button key={s} size="sm" variant="secondary" aria-label={`${x.title}: ${t(`task.st.${s}`)}`} loading={quick.isPending && quick.variables?.id === x.id && quick.variables.status === s} onClick={() => quick.mutate({ id: x.id, status: s })}>{t(`task.st.${s}`)}</Button>))}</div> : null) },
  ]
  const filtered = !!(dq || status || priority || assignee || overdue || mine)
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="min-w-52 flex-1"><Input label={t('common.search')} value={search} onChange={(e) => reset(setSearch)(e.target.value)} suffix={<Search size={15} />} /></div>
        <div className="w-36"><Select label={t('ord.status')} value={status} onChange={(e) => reset(setStatus)(e.target.value)} options={[{ value: '', label: t('common.all') }, ...TASK_STATUSES.map((s) => ({ value: s, label: t(`task.st.${s}`) }))]} /></div>
        <div className="w-32"><Select label={t('task.priority')} value={priority} onChange={(e) => reset(setPriority)(e.target.value)} options={[{ value: '', label: t('common.all') }, ...TASK_PRIORITIES.map((s) => ({ value: s, label: t(`task.pr.${s}`) }))]} /></div>
        {owner && <div className="w-44"><Select label={t('task.assignee')} value={assignee} onChange={(e) => reset(setAssignee)(e.target.value)} options={[{ value: '', label: t('common.all') }, ...(members.data?.results ?? []).map((m) => ({ value: m.id, label: m.user.full_name }))]} /></div>}
        <label className="flex items-center gap-2 pb-2 text-sm"><Switch checked={overdue} onChange={reset(setOverdue)} label={t('task.overdue')} />{t('task.overdue')}</label>
        {owner && <label className="flex items-center gap-2 pb-2 text-sm"><Switch checked={mine} onChange={reset(setMine)} label={t('common.mine')} />{t('common.mine')}</label>}
        {owner && writable && <Button icon={<Plus size={16} />} onClick={() => setOpen('new')}>{t('task.new')}</Button>}
      </div>
      {list.isLoading ? <Skeleton className="h-64" /> : list.isError ? <ErrorState message={apiError(list.error).message} onRetry={() => list.refetch()} />
        : <DataTable compact columns={cols} rows={list.data?.results ?? []} onRowClick={(x) => setOpen(x.id)}
          empty={<EmptyState icon={<ListChecks size={22} />} title={filtered ? t('task.noMatch') : t('task.empty')} text={filtered ? undefined : owner ? t('task.emptyOwner') : t('task.emptyEmployee')}
            action={!filtered && owner && writable ? <Button icon={<Plus size={16} />} onClick={() => setOpen('new')}>{t('task.new')}</Button> : undefined} />} />}
      {list.data && <Pagination page={page} count={list.data.count} pageSize={PAGE} onPage={setPage} />}
      {open !== null && <TaskModal ws={ws} owner={owner} writable={writable} taskId={open === 'new' ? null : open} onClose={() => setOpen(null)} />}
    </div>
  )
}
