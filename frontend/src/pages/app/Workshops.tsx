import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Building2, Check, Mail, Plus, X } from 'lucide-react'
import { api, apiError } from '../../lib/api'
import { fmtAgo } from '../../lib/format'
import { useT } from '../../lib/i18n'
import { useAuth } from '../../stores/auth'
import { useAction, useInvitations, useWorkshops } from '../../hooks/workshops'
import { Button } from '../../components/ui/Button'
import { HoverCard } from '../../components/ui/Card'
import { Input, Textarea } from '../../components/ui/Field'
import { Modal } from '../../components/ui/Modal'
import { EmptyState, ErrorState, Skeleton } from '../../components/ui/Misc'
import { RoleBadge, WorkshopBadge } from '../../components/workshop/common'

function CreateWorkshop({ open, onClose }: { open: boolean; onClose: () => void }) {
  const t = useT(); const nav = useNavigate()
  const [f, setF] = useState({ name: '', description: '', phone: '', email: '', address: '' }); const [errs, setErrs] = useState<Record<string, string>>({})
  const create = useAction((b: typeof f) => api.post<{ id: number }>('/workshops/', b).then((r) => r.data), {
    ok: t('ws.created'), onSuccess: (w) => { setF({ name: '', description: '', phone: '', email: '', address: '' }); onClose(); nav(`/app/workshops/${w.id}`) },
    onError: (e) => setErrs({ ...apiError(e).fields, _: apiError(e).message }) })
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value })
  return (
    <Modal open={open} onClose={onClose} title={t('ws.new')}
      footer={<><Button variant="ghost" onClick={onClose}>{t('common.cancel')}</Button><Button loading={create.isPending} disabled={f.name.trim().length < 2} onClick={() => { setErrs({}); create.mutate(f) }}>{t('common.create')}</Button></>}>
      <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); if (f.name.trim().length >= 2) { setErrs({}); create.mutate(f) } }}>
        <Input label={t('ws.name')} value={f.name} onChange={set('name')} maxLength={120} error={errs.name} autoFocus />
        <Textarea label={t('ws.description')} value={f.description} onChange={set('description')} error={errs.description} />
        <div className="grid gap-4 sm:grid-cols-2"><Input label={t('ws.phone')} value={f.phone} onChange={set('phone')} maxLength={32} error={errs.phone} /><Input label={t('ws.email')} type="email" value={f.email} onChange={set('email')} error={errs.email} /></div>
        <Input label={t('ws.address')} value={f.address} onChange={set('address')} maxLength={255} error={errs.address} />
        {errs._ && !errs.name && Object.keys(errs).length === 1 && <p role="alert" className="text-sm text-danger">{errs._}</p>}
      </form>
    </Modal>
  )
}

export default function Workshops() {
  const t = useT(); const user = useAuth((s) => s.user)!; const [open, setOpen] = useState(false)
  const list = useWorkshops(); const inv = useInvitations()
  const answer = useAction(({ ws, id, status }: { ws: number; id: number; status: 'active' | 'removed' }) => api.patch(`/workshops/${ws}/members/${id}/`, { status }), {})
  const maker = user.role === 'maker'
  return (
    <div className="mx-auto max-w-5xl p-4 sm:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="text-2xl font-bold">{t('side.workshops')}</h1><p className="mt-1 text-sm text-muted">{t('ws.sub')}</p></div>
        {maker && <Button icon={<Plus size={16} />} onClick={() => setOpen(true)}>{t('ws.new')}</Button>}</div>

      {!!inv.data?.results.length && (
        <section aria-label={t('ws.invitations')} className="mt-6 space-y-2">
          <h2 className="text-sm font-semibold">{t('ws.invitations')}</h2>
          {inv.data.results.map((i) => (
            <div key={i.id} className="flex flex-wrap items-center justify-between gap-3 rounded-[14px] border border-primary/30 bg-primary/5 p-4">
              <div className="flex items-center gap-3"><Mail size={18} className="text-primary" /><div><p className="text-sm font-medium">{i.workshop.name}</p><p className="text-xs text-muted">{t('ws.invitedBy').replace('{name}', i.invited_by?.full_name ?? '-')} · {fmtAgo(i.created_at)}</p></div></div>
              <div className="flex gap-2">
                <Button size="sm" icon={<Check size={15} />} loading={answer.isPending && answer.variables?.id === i.id && answer.variables.status === 'active'} onClick={() => answer.mutate({ ws: i.workshop.id, id: i.id, status: 'active' })}>{t('ws.accept')}</Button>
                <Button size="sm" variant="secondary" icon={<X size={15} />} disabled={answer.isPending} onClick={() => answer.mutate({ ws: i.workshop.id, id: i.id, status: 'removed' })}>{t('ws.decline')}</Button></div>
            </div>))}
        </section>)}

      <div className="mt-6">
        {list.isLoading ? <div className="grid gap-3 sm:grid-cols-2">{[0, 1].map((i) => <Skeleton key={i} className="h-28" />)}</div>
          : list.isError ? <ErrorState message={t('ws.loadErr')} onRetry={() => list.refetch()} />
          : list.data?.results.length ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{list.data.results.map((w) => (
              <Link key={w.id} to={`/app/workshops/${w.id}`} className="block rounded-[14px] focus-visible:outline-offset-4">
                <HoverCard className="h-full p-4"><div className="flex items-start justify-between gap-2"><p className="truncate font-semibold">{w.name}</p><WorkshopBadge s={w.status} /></div>
                  <p className="mt-1 line-clamp-2 min-h-8 text-xs text-muted">{w.description || w.address || ' '}</p>
                  <div className="mt-3 flex items-center justify-between text-xs text-muted">{w.my_role && <RoleBadge r={w.my_role} />}<span>{t('ws.owner')}: {w.owner?.full_name ?? '-'}</span></div></HoverCard></Link>))}</div>)
          : <EmptyState icon={<Building2 size={22} />} title={t('ws.empty')} text={maker ? t('ws.emptyMaker') : t('ws.emptyOther')} action={maker ? <Button icon={<Plus size={16} />} onClick={() => setOpen(true)}>{t('ws.new')}</Button> : undefined} />}
      </div>
      <CreateWorkshop open={open} onClose={() => setOpen(false)} />
    </div>
  )
}
