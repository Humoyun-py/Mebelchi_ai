import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Activity, Building2, CreditCard, Flag, FolderKanban, HardDrive, History, Send, Users } from 'lucide-react'
import { api, apiError } from '../../lib/api'
import { fmtAgo, fmtBytes, fmtDateTime } from '../../lib/format'
import type { AuditEntry, Page } from '../../lib/types'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input, Select, Switch, Textarea } from '../../components/ui/Field'
import { Badge, type Column, DataTable, ErrorState, Pagination, Skeleton, Stat } from '../../components/ui/Misc'
import { Tabs } from '../../components/ui/Tabs'
import { toast } from '../../components/ui/Toast'
import { useDebounced } from '../../hooks/queries'
import { WorkshopsTab } from './WorkshopsTab'

type Tab = 'overview' | 'users' | 'workshops' | 'projects' | 'billing' | 'logs' | 'audit' | 'features' | 'storage'
const get = async <T,>(url: string, params?: object) => (await api.get<T>(`/admin-api/${url}`, { params })).data

interface Stats { users: { total: number; active_30d: number; by_role: { role: string; n: number }[] }; projects: { total: number; active: number }; subscriptions: { plan__name: string; n: number }[]
  payments: { pending: number; paid: number; revenue_usd: string }; storage_bytes: number; signups_14d: { date: string; count: number }[]; usage_14d: { kind: string; n: number }[]; errors_24h: number }

function Bars({ data, label }: { data: { k: string; v: number }[]; label: string }) {
  const max = Math.max(1, ...data.map((d) => d.v))
  return (
    <div role="img" aria-label={label} className="space-y-2">{data.length ? data.map((d) => <div key={d.k} className="flex items-center gap-3 text-xs"><span className="w-28 shrink-0 truncate text-muted">{d.k}</span><div className="h-2.5 flex-1 rounded-full bg-card2"><div className="h-full rounded-full bg-primary" style={{ width: `${(100 * d.v) / max}%` }} /></div><span className="num w-8 text-right">{d.v}</span></div>) : <p className="text-sm text-muted">No data yet.</p>}</div>
  )
}

function Overview() {
  const { data, isError, refetch } = useQuery({ queryKey: ['admin', 'stats'], queryFn: () => get<Stats>('stats/') })
  if (isError) return <ErrorState message="Could not load statistics." onRetry={refetch} />
  if (!data) return <Skeleton className="h-64" />
  return (
    <div className="space-y-5"><div className="grid grid-cols-2 gap-3 lg:grid-cols-4"><Stat label="Users" value={data.users.total} hint={`${data.users.active_30d} active in 30 days`} /><Stat label="Projects" value={data.projects.total} hint={`${data.projects.active} active`} /><Stat label="Storage" value={fmtBytes(data.storage_bytes)} /><Stat label="Errors (24h)" value={data.errors_24h} /></div>
      <div className="grid gap-4 lg:grid-cols-2"><Card className="p-5"><h3 className="mb-4 font-semibold">Sign-ups, last 14 days</h3><Bars label="Signups per day" data={data.signups_14d.map((s) => ({ k: s.date.slice(5), v: s.count }))} /></Card>
        <Card className="p-5"><h3 className="mb-4 font-semibold">Feature usage, last 14 days</h3><Bars label="Usage by feature" data={data.usage_14d.map((u) => ({ k: u.kind.replace(/_/g, ' '), v: u.n }))} /></Card>
        <Card className="p-5"><h3 className="mb-4 font-semibold">Subscriptions by plan</h3><Bars label="Subscriptions" data={data.subscriptions.map((s) => ({ k: s.plan__name, v: s.n }))} /></Card>
        <Card className="p-5"><h3 className="mb-4 font-semibold">Payments</h3><dl className="space-y-2 text-sm">{[['Pending', data.payments.pending], ['Paid', data.payments.paid], ['Confirmed revenue', `$${data.payments.revenue_usd}`]].map(([k, v]) => <div key={k} className="flex justify-between"><dt className="text-muted">{k}</dt><dd className="num">{v}</dd></div>)}</dl></Card></div></div>
  )
}

function useList<T>(path: string, extra: object = {}) {
  const [q, setQ] = useState(''); const [page, setPage] = useState(1); const dq = useDebounced(q, 300)
  const query = useQuery({ queryKey: ['admin', path, dq, page, extra], queryFn: () => get<Page<T>>(path, { search: dq, page, ...extra }) })
  return { q, setQ: (v: string) => { setQ(v); setPage(1) }, page, setPage, ...query }
}
const Toolbar = ({ q, setQ }: { q: string; setQ: (v: string) => void }) => <div className="mb-4 max-w-xs"><Input label="Search" value={q} onChange={(e) => setQ(e.target.value)} /></div>

interface AUser { id: number; email: string; first_name: string; last_name: string; role: string; is_active: boolean; is_staff: boolean; date_joined: string; plan: string; project_count: number }
function UsersTab() {
  const qc = useQueryClient(); const l = useList<AUser>('users/')
  const patch = useMutation({ mutationFn: ({ id, ...b }: { id: number } & Partial<AUser>) => api.patch(`/admin-api/users/${id}/`, b), onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin', 'users/'] }); toast.success('Updated') }, onError: (e) => toast.error(apiError(e).message) })
  const cols: Column<AUser>[] = [
    { key: 'e', header: 'User', render: (u) => <div><p className="font-medium">{u.first_name} {u.last_name}</p><p className="text-xs text-muted">{u.email}</p></div> },
    { key: 'r', header: 'Role', className: 'hidden sm:table-cell', render: (u) => (
      <select aria-label={`Role ${u.email}`} value={u.role} disabled={patch.isPending} onChange={(e) => patch.mutate({ id: u.id, role: e.target.value })} className="h-8 rounded-lg border border-line bg-card2 px-2 text-sm">
        <option value="homeowner">homeowner</option><option value="maker">maker</option><option value="workshop">workshop</option></select>) }, { key: 'p', header: 'Plan', className: 'hidden md:table-cell', render: (u) => u.plan },
    { key: 'c', header: 'Projects', className: 'num hidden md:table-cell', render: (u) => u.project_count }, { key: 'j', header: 'Joined', className: 'hidden lg:table-cell text-muted', render: (u) => fmtAgo(u.date_joined) },
    { key: 'a', header: 'Active', render: (u) => <Switch label={`Active ${u.email}`} checked={u.is_active} onChange={(v) => patch.mutate({ id: u.id, is_active: v })} /> },
    { key: 's', header: 'Admin', render: (u) => <Switch label={`Admin ${u.email}`} checked={u.is_staff} onChange={(v) => patch.mutate({ id: u.id, is_staff: v })} /> }]
  return <div><Toolbar q={l.q} setQ={l.setQ} />{l.isLoading ? <Skeleton className="h-64" /> : <DataTable columns={cols} rows={l.data?.results ?? []} />}{l.data && <Pagination page={l.page} count={l.data.count} pageSize={24} onPage={l.setPage} />}</div>
}

interface AProject { id: number; name: string; category: string; status: string; owner_email: string; updated_at: string }
function ProjectsTab() {
  const l = useList<AProject>('projects/')
  const cols: Column<AProject>[] = [{ key: 'n', header: 'Project', render: (p) => <span className="font-medium">{p.name}</span> }, { key: 'o', header: 'Owner', className: 'text-muted', render: (p) => p.owner_email }, { key: 'c', header: 'Category', className: 'hidden sm:table-cell', render: (p) => <Badge>{p.category}</Badge> },
    { key: 's', header: 'Status', render: (p) => <Badge tone={p.status === 'active' ? 'success' : 'neutral'}>{p.status}</Badge> }, { key: 'u', header: 'Updated', className: 'hidden md:table-cell text-muted', render: (p) => fmtAgo(p.updated_at) }]
  return <div><Toolbar q={l.q} setQ={l.setQ} />{l.isLoading ? <Skeleton className="h-64" /> : <DataTable columns={cols} rows={l.data?.results ?? []} />}{l.data && <Pagination page={l.page} count={l.data.count} pageSize={24} onPage={l.setPage} />}</div>
}

interface ASub { id: number; email: string; plan_slug: string; plan_name: string; status: string }
interface APay { id: number; email: string; plan_name: string; amount: string; status: string; created_at: string }
function BillingTab() {
  const qc = useQueryClient(); const subs = useList<ASub>('subscriptions/'); const pays = useList<APay>('payments/')
  const plans = useQuery({ queryKey: ['plans'], queryFn: async () => (await api.get<{ slug: string; name: string }[]>('/subscriptions/plans/')).data })
  const inval = () => qc.invalidateQueries({ queryKey: ['admin'] })
  const setPlan = useMutation({ mutationFn: ({ id, plan_slug }: { id: number; plan_slug: string }) => api.patch(`/admin-api/subscriptions/${id}/`, { plan_slug }), onSuccess: () => { inval(); toast.success('Plan updated') }, onError: (e) => toast.error(apiError(e).message) })
  const act = useMutation({ mutationFn: ({ id, a }: { id: number; a: 'confirm' | 'reject' }) => api.post(`/admin-api/payments/${id}/${a}/`), onSuccess: () => { inval(); toast.success('Payment updated') }, onError: (e) => toast.error(apiError(e).message) })
  const sc: Column<ASub>[] = [{ key: 'e', header: 'User', render: (s) => s.email }, { key: 'p', header: 'Plan', render: (s) => <div className="w-40"><Select label="" aria-label={`Plan for ${s.email}`} value={s.plan_slug} onChange={(e) => setPlan.mutate({ id: s.id, plan_slug: e.target.value })} options={plans.data?.map((p) => ({ value: p.slug, label: p.name })) ?? []} /></div> }, { key: 's', header: 'Status', render: (s) => <Badge tone="success">{s.status}</Badge> }]
  const pc: Column<APay>[] = [{ key: 'e', header: 'User', render: (p) => p.email }, { key: 'p', header: 'Plan', render: (p) => p.plan_name }, { key: 'a', header: 'Amount', className: 'num', render: (p) => `$${p.amount}` }, { key: 'd', header: 'Date', className: 'hidden sm:table-cell text-muted', render: (p) => fmtAgo(p.created_at) },
    { key: 's', header: 'Status', render: (p) => <Badge tone={p.status === 'paid' ? 'success' : p.status === 'pending' ? 'warning' : 'danger'}>{p.status}</Badge> },
    { key: 'x', header: '', render: (p) => p.status === 'pending' ? <div className="flex gap-1"><Button size="sm" onClick={() => act.mutate({ id: p.id, a: 'confirm' })}>Confirm</Button><Button size="sm" variant="ghost" onClick={() => act.mutate({ id: p.id, a: 'reject' })}>Reject</Button></div> : null }]
  return <div className="space-y-8"><section><h3 className="mb-3 font-semibold">Payment records</h3>{pays.isLoading ? <Skeleton className="h-40" /> : <DataTable columns={pc} rows={pays.data?.results ?? []} />}</section>
    <section><h3 className="mb-3 font-semibold">Subscriptions</h3><Toolbar q={subs.q} setQ={subs.setQ} />{subs.isLoading ? <Skeleton className="h-40" /> : <DataTable columns={sc} rows={subs.data?.results ?? []} />}{subs.data && <Pagination page={subs.page} count={subs.data.count} pageSize={24} onPage={subs.setPage} />}</section></div>
}

interface ALog { id: number; level: string; message: string; status_code: number | null; created_at: string }
function LogsTab() {
  const l = useList<ALog>('logs/')
  const cols: Column<ALog>[] = [{ key: 't', header: 'Time', className: 'text-muted whitespace-nowrap', render: (x) => fmtAgo(x.created_at) }, { key: 'l', header: 'Level', render: (x) => <Badge tone="danger">{x.level}</Badge> }, { key: 'm', header: 'Message', className: 'font-mono text-xs', render: (x) => x.message }]
  return <div><Toolbar q={l.q} setQ={l.setQ} />{l.isLoading ? <Skeleton className="h-64" /> : <DataTable columns={cols} rows={l.data?.results ?? []} empty={<Card className="p-8 text-center text-sm text-muted">No server errors recorded.</Card>} />}{l.data && <Pagination page={l.page} count={l.data.count} pageSize={24} onPage={l.setPage} />}</div>
}


const AUDIT_ACTIONS = ['create', 'update', 'delete', 'login', 'logout', 'password']
/** Append-only audit trail (read-only). Filters are sent to the server; nothing here can change an entry. */
function AuditTab() {
  const [action, setAction] = useState(''); const [event, setEvent] = useState(''); const [model, setModel] = useState(''); const [actor, setActor] = useState('')
  const devent = useDebounced(event, 300); const dmodel = useDebounced(model, 300); const dactor = useDebounced(actor, 300)
  const l = useList<AuditEntry>('audit-logs/', { action, event: devent, model: dmodel, actor_email: dactor })
  const cols: Column<AuditEntry>[] = [
    { key: 't', header: 'Time', className: 'whitespace-nowrap text-muted', render: (e) => <span title={e.created_at}>{fmtDateTime(e.created_at)}</span> },
    { key: 'a', header: 'Actor', render: (e) => (e.actor_email ? <span>{e.actor_email}</span> : <span className="text-muted">system</span>) },
    { key: 'e', header: 'Event', render: (e) => <div className="flex flex-wrap items-center gap-1"><Badge tone={e.action === 'delete' ? 'danger' : e.action === 'create' ? 'success' : 'neutral'}>{e.action}</Badge>{e.event && <code className="text-xs text-muted">{e.event}</code>}</div> },
    { key: 'o', header: 'Object', render: (e) => <div className="min-w-0"><p className="truncate">{e.object_repr || '-'}</p><p className="text-xs text-muted">{e.model}{e.object_id ? ` #${e.object_id}` : ''}</p></div> },
    { key: 'i', header: 'IP', className: 'num hidden text-muted lg:table-cell', render: (e) => e.ip ?? '-' },
    { key: 'c', header: 'Changes', render: (e) => { const keys = Object.keys(e.changes ?? {}); return keys.length ? (
      <details className="text-xs"><summary className="cursor-pointer text-primary">{keys.length} field{keys.length > 1 ? 's' : ''}</summary>
        <ul className="mt-1 space-y-0.5">{keys.map((k) => { const c = (e.changes as Record<string, { old?: unknown; new?: unknown }>)[k]; return <li key={k}><span className="text-muted">{k}:</span> {c && typeof c === 'object' && 'old' in c ? <>{JSON.stringify(c.old)} → {JSON.stringify(c.new)}</> : JSON.stringify(c)}</li> })}</ul></details>) : <span className="text-muted">-</span> } },
  ]
  return (
    <div><div className="mb-4 flex flex-wrap items-end gap-3">
      <div className="min-w-48 flex-1"><Input label="Search actor, object or path" value={l.q} onChange={(e) => l.setQ(e.target.value)} /></div>
      <div className="w-36"><Select label="Action" value={action} onChange={(e) => { setAction(e.target.value); l.setPage(1) }} options={[{ value: '', label: 'All' }, ...AUDIT_ACTIONS.map((a) => ({ value: a, label: a }))]} /></div>
      <div className="w-44"><Input label="Event (e.g. order.status_changed)" value={event} onChange={(e) => { setEvent(e.target.value); l.setPage(1) }} /></div>
      <div className="w-40"><Input label="Model (app.model)" value={model} onChange={(e) => { setModel(e.target.value); l.setPage(1) }} /></div>
      <div className="w-44"><Input label="Actor email" value={actor} onChange={(e) => { setActor(e.target.value); l.setPage(1) }} /></div></div>
      {l.isError ? <ErrorState message="Could not load the audit log." onRetry={() => l.refetch()} /> : l.isLoading ? <Skeleton className="h-64" /> :
        <DataTable columns={cols} rows={l.data?.results ?? []} empty={<Card className="p-8 text-center text-sm text-muted">No audit entries match.</Card>} />}
      {l.data && <Pagination page={l.page} count={l.data.count} pageSize={24} onPage={l.setPage} />}</div>
  )
}

interface Flag { id: number; key: string; description: string; enabled: boolean }
function FeaturesTab() {
  const qc = useQueryClient(); const flags = useQuery({ queryKey: ['admin', 'features'], queryFn: () => get<Flag[]>('features/') }); const [title, setTitle] = useState(''); const [body, setBody] = useState('')
  const toggle = useMutation({ mutationFn: (f: Flag) => api.patch(`/admin-api/features/${f.id}/`, { enabled: !f.enabled }), onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'features'] }), onError: (e) => toast.error(apiError(e).message) })
  const send = useMutation({ mutationFn: () => api.post<{ sent: number }>('/admin-api/broadcast/', { title, body }), onSuccess: (r) => { toast.success(`Sent to ${r.data.sent} users`); setTitle(''); setBody('') }, onError: (e) => toast.error(apiError(e).message) })
  return (
    <div className="grid gap-5 lg:grid-cols-2"><Card className="divide-y divide-line">{flags.data?.map((f) => <div key={f.id} className="flex items-center justify-between gap-3 p-4"><div><p className="font-medium">{f.key}</p><p className="text-xs text-muted">{f.description}</p></div><Switch label={`Feature ${f.key}`} checked={f.enabled} onChange={() => toggle.mutate(f)} /></div>) ?? <Skeleton className="h-40" />}</Card>
      <Card className="space-y-4 p-5"><h3 className="font-semibold">Broadcast notification</h3><Input label="Title" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={160} /><Textarea label="Message" value={body} onChange={(e) => setBody(e.target.value)} /><Button icon={<Send size={16} />} loading={send.isPending} disabled={!title.trim()} onClick={() => send.mutate()}>Send to all users</Button></Card></div>
  )
}

function StorageTab() {
  const { data } = useQuery({ queryKey: ['admin', 'storage'], queryFn: () => get<{ email: string; image_bytes: number; images: number }[]>('storage/') })
  return <Card className="p-5"><h3 className="mb-4 font-semibold">Top users by image storage</h3>{data ? <Bars label="Storage by user" data={data.map((d) => ({ k: d.email, v: Math.round(d.image_bytes / 1024) }))} /> : <Skeleton className="h-40" />}<p className="mt-3 text-xs text-muted">Values in KB.</p></Card>
}

export default function Admin() {
  const [tab, setTab] = useState<Tab>('overview')
  return (
    <div className="mx-auto max-w-6xl p-4 sm:p-8"><h1 className="text-2xl font-bold">Administration</h1><p className="mt-1 text-sm text-muted">Platform-wide data. Access is restricted to staff.</p>
      <div className="mt-5"><Tabs tabs={[{ id: 'overview', label: 'Overview', icon: <Activity size={15} /> }, { id: 'users', label: 'Users', icon: <Users size={15} /> }, { id: 'workshops', label: 'Workshops', icon: <Building2 size={15} /> }, { id: 'projects', label: 'Projects', icon: <FolderKanban size={15} /> }, { id: 'billing', label: 'Billing', icon: <CreditCard size={15} /> }, { id: 'logs', label: 'Logs', icon: <Activity size={15} /> }, { id: 'audit', label: 'Audit log', icon: <History size={15} /> }, { id: 'features', label: 'Features', icon: <Flag size={15} /> }, { id: 'storage', label: 'Storage', icon: <HardDrive size={15} /> }]} value={tab} onChange={setTab} /></div>
      <div className="mt-6">{{ overview: <Overview />, users: <UsersTab />, workshops: <WorkshopsTab />, projects: <ProjectsTab />, billing: <BillingTab />, logs: <LogsTab />, audit: <AuditTab />, features: <FeaturesTab />, storage: <StorageTab /> }[tab]}</div></div>
  )
}
