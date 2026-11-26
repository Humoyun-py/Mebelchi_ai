import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, apiError } from '../../lib/api'
import { fmtAgo, fmtDateTime } from '../../lib/format'
import { workshopTone } from '../../lib/workshop'
import type { AuditEntry, Page, WorkshopStatus } from '../../lib/types'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input, Select, Textarea } from '../../components/ui/Field'
import { Modal } from '../../components/ui/Modal'
import { Badge, type Column, DataTable, ErrorState, Pagination, Skeleton } from '../../components/ui/Misc'
import { toast } from '../../components/ui/Toast'
import { useDebounced } from '../../hooks/queries'

interface AWorkshop {
  id: number; name: string; kind: string; city: string; slug: string; status: WorkshopStatus; review_note: string; owner: number; owner_email: string
  member_count: number; order_count: number; created_at: string; updated_at: string
}
type Decision = 'approve' | 'reject' | 'suspend'

const STATUSES: ('' | WorkshopStatus)[] = ['pending', 'active', 'rejected', 'suspended', 'inactive', '']
/** What an administrator may do next. The server enforces the same rules and answers 400 for anything else. */
const actionsFor = (s: WorkshopStatus): { id: Decision; label: string; tone?: 'danger' }[] => ({
  pending: [{ id: 'approve' as const, label: 'Approve' }, { id: 'reject' as const, label: 'Reject', tone: 'danger' as const }],
  rejected: [{ id: 'approve' as const, label: 'Approve anyway' }],
  active: [{ id: 'suspend' as const, label: 'Suspend', tone: 'danger' as const }],
  suspended: [{ id: 'approve' as const, label: 'Reactivate' }],
  inactive: [{ id: 'approve' as const, label: 'Activate' }],
})[s]

function History({ ws, onClose }: { ws: AWorkshop; onClose: () => void }) {
  const q = useQuery({ queryKey: ['admin', 'workshop-history', ws.id], queryFn: async () => (await api.get<Page<AuditEntry>>('/admin-api/audit-logs/', { params: { model: 'workshops.workshop', object_id: ws.id } })).data })
  return (
    <Modal open onClose={onClose} title={`History: ${ws.name}`} wide>
      {q.isError ? <ErrorState message="Could not load the history." onRetry={() => q.refetch()} /> : q.isLoading ? <Skeleton className="h-32" /> : (
        <ol className="space-y-3 text-sm" aria-label="Workshop history">
          {(q.data?.results ?? []).map((e) => {
            const ch = e.changes as Record<string, { old?: unknown; new?: unknown }>
            return (
              <li key={e.id} className="rounded-lg border border-line p-3">
                <div className="flex flex-wrap items-center gap-2"><code className="text-xs">{e.event || e.action}</code><span className="text-muted">{e.actor_email || 'system'}</span><span className="ml-auto text-xs text-muted" title={e.created_at}>{fmtDateTime(e.created_at)}</span></div>
                {ch?.status && <p className="mt-1 text-xs text-muted">status: {String(ch.status.old ?? '-')} → {String(ch.status.new)}</p>}
                {ch?.review_note?.new ? <p className="mt-1 text-xs">Note: {String(ch.review_note.new)}</p> : null}
              </li>
            )
          })}
          {!q.data?.results.length && <li className="text-muted">No history yet.</li>}
        </ol>
      )}
    </Modal>
  )
}

export function WorkshopsTab() {
  const qc = useQueryClient()
  const [status, setStatus] = useState<'' | WorkshopStatus>('pending'); const [q, setQ] = useState(''); const [page, setPage] = useState(1); const dq = useDebounced(q, 300)
  const [ask, setAsk] = useState<{ ws: AWorkshop; action: Decision } | null>(null); const [note, setNote] = useState(''); const [err, setErr] = useState('')
  const [hist, setHist] = useState<AWorkshop | null>(null)
  const list = useQuery({ queryKey: ['admin', 'workshops/', status, dq, page], queryFn: async () => (await api.get<Page<AWorkshop>>('/admin-api/workshops/', { params: { status, search: dq, page } })).data })
  const decide = useMutation({
    mutationFn: ({ ws, action, note }: { ws: AWorkshop; action: Decision; note: string }) => api.post(`/admin-api/workshops/${ws.id}/${action}/`, note ? { note } : {}),
    onSuccess: (_r, v) => { qc.invalidateQueries({ queryKey: ['admin'] }); toast.success({ approve: 'Approved', reject: 'Rejected', suspend: 'Suspended' }[v.action]); setAsk(null); setNote(''); setErr('') },
    onError: (e) => { const m = apiError(e); setErr(m.fields.note || m.message); if (!ask) toast.error(m.message) },
  })
  const start = (ws: AWorkshop, action: Decision) => { setErr(''); setNote(''); if (action === 'approve') decide.mutate({ ws, action, note: '' }); else setAsk({ ws, action }) }
  const cols: Column<AWorkshop>[] = [
    { key: 'n', header: 'Workshop', render: (w) => <div><p className="font-medium">{w.name}</p><p className="text-xs text-muted">{[w.city, w.slug].filter(Boolean).join(' · ')}</p></div> },
    { key: 'o', header: 'Owner', className: 'hidden sm:table-cell text-muted', render: (w) => w.owner_email },
    { key: 's', header: 'Status', render: (w) => <div><Badge tone={workshopTone[w.status]}>{w.status}</Badge>{w.review_note && <p className="mt-1 max-w-56 text-xs text-muted">{w.review_note}</p>}</div> },
    { key: 'm', header: 'Members / orders', className: 'num hidden md:table-cell', render: (w) => `${w.member_count} / ${w.order_count}` },
    { key: 'c', header: 'Created', className: 'hidden lg:table-cell text-muted', render: (w) => fmtAgo(w.created_at) },
    { key: 'a', header: 'Actions', render: (w) => (
      <div className="flex flex-wrap gap-2">
        {actionsFor(w.status).map((a) => <Button key={a.id} size="sm" variant={a.tone === 'danger' ? 'danger' : 'primary'} disabled={decide.isPending} aria-label={`${a.label} ${w.name}`} onClick={() => start(w, a.id)}>{a.label}</Button>)}
        <Button size="sm" variant="ghost" aria-label={`History ${w.name}`} onClick={() => setHist(w)}>History</Button>
      </div>) },
  ]
  const reject = ask?.action === 'reject'
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="min-w-48 max-w-xs flex-1"><Input label="Search workshop or owner" value={q} onChange={(e) => { setQ(e.target.value); setPage(1) }} /></div>
        <div className="w-40"><Select label="Status" value={status} onChange={(e) => { setStatus(e.target.value as '' | WorkshopStatus); setPage(1) }} options={STATUSES.map((s) => ({ value: s, label: s || 'All' }))} /></div>
      </div>
      {list.isError ? <ErrorState message="Could not load workshops." onRetry={() => list.refetch()} /> : list.isLoading ? <Skeleton className="h-64" /> :
        <DataTable columns={cols} rows={list.data?.results ?? []} empty={<Card className="p-8 text-center text-sm text-muted">No workshops match.</Card>} />}
      {list.data && <Pagination page={page} count={list.data.count} pageSize={24} onPage={setPage} />}
      {ask && (
        <Modal open onClose={() => setAsk(null)} title={`${reject ? 'Reject' : 'Suspend'}: ${ask.ws.name}`}
          footer={<><Button variant="ghost" onClick={() => setAsk(null)}>Cancel</Button><Button variant="danger" loading={decide.isPending} disabled={reject && !note.trim()} onClick={() => decide.mutate({ ws: ask.ws, action: ask.action, note })}>{reject ? 'Reject application' : 'Suspend workshop'}</Button></>}>
          <Textarea label={reject ? 'Reason (shown to the owner)' : 'Note (optional, shown to the owner)'} value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} error={err} />
        </Modal>
      )}
      {hist && <History ws={hist} onClose={() => setHist(null)} />}
    </div>
  )
}
