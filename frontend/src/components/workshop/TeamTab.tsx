import { useState } from 'react'
import { Crown, LogOut, UserMinus, UserPlus, Users } from 'lucide-react'
import { api, apiError } from '../../lib/api'
import { fmtDate } from '../../lib/format'
import { useT } from '../../lib/i18n'
import { useAuth } from '../../stores/auth'
import type { Member, Workshop } from '../../lib/types'
import { useAction, useMembers } from '../../hooks/workshops'
import { Button } from '../ui/Button'
import { Input, Select } from '../ui/Field'
import { ConfirmDialog } from '../ui/Modal'
import { type Column, DataTable, EmptyState, ErrorState, Skeleton } from '../ui/Misc'
import { MemberStatusBadge, RoleBadge } from './common'

export function TeamTab({ ws, owner, writable }: { ws: Workshop; owner: boolean; writable: boolean }) {
  const t = useT(); const me = useAuth((s) => s.user)!
  const [status, setStatus] = useState(''); const [email, setEmail] = useState(''); const [emailErr, setEmailErr] = useState('')
  const [ask, setAsk] = useState<{ kind: 'remove' | 'leave' | 'transfer'; m: Member } | null>(null)
  const list = useMembers(ws.id, { status })
  const invite = useAction((e: string) => api.post(`/workshops/${ws.id}/members/`, { email: e }), { ok: t('team.invited'), onSuccess: () => { setEmail(''); setEmailErr('') }, onError: (e) => setEmailErr(apiError(e).fields.email || apiError(e).message) })
  const act = useAction(async ({ kind, m }: { kind: 'remove' | 'leave' | 'transfer'; m: Member }) => {
    if (kind === 'remove') return api.delete(`/workshops/${ws.id}/members/${m.id}/`)
    if (kind === 'leave') return api.patch(`/workshops/${ws.id}/members/${m.id}/`, { status: 'removed' })
    return api.patch(`/workshops/${ws.id}/members/${m.id}/`, { role: 'owner', confirm_transfer: true })
  }, { ok: t('team.done') })
  const run = () => { if (ask) act.mutate(ask, { onSettled: () => setAsk(null) }) }
  const cols: Column<Member>[] = [
    { key: 'n', header: t('team.person'), render: (m) => <div className="min-w-0"><p className="truncate font-medium">{m.user.full_name}{m.user.id === me.id && <span className="ml-1 text-xs text-muted">({t('team.you')})</span>}</p>{m.user.email && <p className="truncate text-xs text-muted">{m.user.email}</p>}</div> },
    { key: 'r', header: t('team.role'), render: (m) => <div className="flex flex-wrap gap-1"><RoleBadge r={m.role} /><MemberStatusBadge s={m.status} /></div> },
    { key: 'j', header: t('team.joined'), className: 'num hidden whitespace-nowrap md:table-cell text-muted', render: (m) => (m.joined_at ? fmtDate(m.joined_at) : '-') },
    { key: 'x', header: '', render: (m) => {
      if (!writable && !(m.user.id === me.id && m.role !== 'owner' && m.status === 'active')) return null
      return <div className="flex justify-end gap-1">
        {owner && writable && m.role === 'employee' && m.status === 'active' && <Button size="sm" variant="ghost" icon={<Crown size={14} />} aria-label={`${t('team.transfer')}: ${m.user.full_name}`} onClick={() => setAsk({ kind: 'transfer', m })}>{t('team.transfer')}</Button>}
        {owner && writable && m.role === 'employee' && m.status !== 'removed' && <Button size="sm" variant="ghost" icon={<UserMinus size={14} />} aria-label={`${t('team.remove')}: ${m.user.full_name}`} onClick={() => setAsk({ kind: 'remove', m })}>{t('team.remove')}</Button>}
        {m.user.id === me.id && m.role !== 'owner' && m.status === 'active' && <Button size="sm" variant="ghost" icon={<LogOut size={14} />} onClick={() => setAsk({ kind: 'leave', m })}>{t('team.leave')}</Button>}
      </div> } },
  ]
  const msg = ask && { remove: t('team.removeMsg').replace('{name}', ask.m.user.full_name), leave: t('team.leaveMsg'), transfer: t('team.transferMsg').replace('{name}', ask.m.user.full_name) }[ask.kind]
  return (
    <div className="space-y-5">
      {owner && writable && (
        <form className="flex flex-wrap items-start gap-3 rounded-[14px] border border-line bg-card p-4" onSubmit={(e) => { e.preventDefault(); if (email.trim()) invite.mutate(email.trim()) }}>
          <div className="min-w-60 flex-1"><Input label={t('team.inviteEmail')} type="email" value={email} onChange={(e) => { setEmail(e.target.value); setEmailErr('') }} error={emailErr} hint={t('team.inviteHint')} /></div>
          <Button type="submit" icon={<UserPlus size={16} />} className="mt-0.5" loading={invite.isPending} disabled={!email.trim()}>{t('team.invite')}</Button>
        </form>)}
      {owner && <div className="w-48"><Select label={t('ord.status')} value={status} onChange={(e) => setStatus(e.target.value)} options={[{ value: '', label: t('common.all') }, { value: 'active', label: t('mstatus.active') }, { value: 'invited', label: t('mstatus.invited') }, { value: 'removed', label: t('mstatus.removed') }]} /></div>}
      {list.isLoading ? <Skeleton className="h-48" /> : list.isError ? <ErrorState message={apiError(list.error).message} onRetry={() => list.refetch()} />
        : <DataTable compact columns={cols} rows={list.data?.results ?? []} empty={<EmptyState icon={<Users size={22} />} title={t('team.empty')} />} />}
      {!owner && <p className="text-xs text-muted">{t('team.privacy')}</p>}
      <ConfirmDialog open={!!ask} onClose={() => setAsk(null)} title={ask ? t(`team.${ask.kind}Title`) : ''} message={msg ?? ''} confirmLabel={ask ? t(`team.${ask.kind}Do`) : ''} cancelLabel={t('common.cancel')} loading={act.isPending} onConfirm={run} />
    </div>
  )
}
