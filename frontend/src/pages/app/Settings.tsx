import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, CreditCard, Globe, HardDrive, Lock, MessageCircle, Moon, Palette, Sun, Trash2, User as UserIcon } from 'lucide-react'
import clsx from 'clsx'
import { api, apiError } from '../../lib/api'
import { fmtAgo, fmtBytes, fmtDate } from '../../lib/format'
import type { Plan, Usage, User } from '../../lib/types'
import { useAuth } from '../../stores/auth'
import { useUI } from '../../stores/ui'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input, Select, Switch } from '../../components/ui/Field'
import { Badge, Progress, Skeleton, Stat } from '../../components/ui/Misc'
import { FileUploader } from '../../components/ui/FileUploader'
import { Tabs } from '../../components/ui/Tabs'
import { toast } from '../../components/ui/Toast'

type Tab = 'profile' | 'appearance' | 'language' | 'notifications' | 'telegram' | 'security' | 'subscription' | 'storage'
const TABS = [['profile', 'Profile', UserIcon], ['appearance', 'Appearance', Palette], ['language', 'Language', Globe], ['notifications', 'Notifications', Bell], ['telegram', 'Telegram', MessageCircle], ['security', 'Security', Lock], ['subscription', 'Subscription', CreditCard], ['storage', 'Storage', HardDrive]] as const

function useProfile() {
  const setUser = useAuth((s) => s.setUser)
  return useMutation({ mutationFn: async (patch: Partial<User>) => (await api.patch<User>('/users/me/', patch)).data, onSuccess: (u) => { setUser(u); toast.success('Saved') }, onError: (e) => toast.error(apiError(e).message) })
}

function Profile() {
  const user = useAuth((s) => s.user)!; const setUser = useAuth((s) => s.setUser); const save = useProfile()
  const [f, setF] = useState({ first_name: user.first_name, last_name: user.last_name, phone: user.phone }); const [errs, setErrs] = useState<Record<string, string>>({})
  const av = useMutation({ mutationFn: async (file: File) => { const fd = new FormData(); fd.append('avatar', file); return (await api.post<User>('/users/me/avatar/', fd)).data }, onSuccess: (u) => { setUser(u); toast.success('Photo updated') }, onError: (e) => toast.error(apiError(e).message) })
  const rm = useMutation({ mutationFn: () => api.delete('/users/me/avatar/'), onSuccess: async () => setUser((await api.get<User>('/users/me/')).data) })
  const role = useMutation({ mutationFn: async (r: string) => (await api.post<User>('/users/me/role/', { role: r })).data, onSuccess: (u) => { setUser(u); toast.success('Workspace changed') } })
  const submit = () => { const e: Record<string, string> = {}; if (!f.first_name.trim()) e.first_name = 'Required.'; if (!f.last_name.trim()) e.last_name = 'Required.'; if (f.phone && !/^\+?[0-9\s()-]{7,20}$/.test(f.phone)) e.phone = 'Enter a valid phone number.'; setErrs(e); if (!Object.keys(e).length) save.mutate(f) }
  return (
    <div className="space-y-5">
      <Card className="flex flex-wrap items-center gap-5 p-5"><div className="flex h-20 w-20 items-center justify-center overflow-hidden rounded-full bg-primary text-2xl font-semibold text-on-primary">{user.avatar_url ? <img src={user.avatar_url} alt="Profile" className="h-full w-full object-cover" /> : (user.first_name[0] + user.last_name[0]).toUpperCase()}</div>
        <div className="w-56"><FileUploader accept="image/png,image/jpeg,image/webp" maxMB={5} onFiles={(x) => av.mutate(x[0])} disabled={av.isPending} label="Upload photo" /></div>
        {user.avatar_url && <Button variant="ghost" icon={<Trash2 size={16} />} onClick={() => rm.mutate()}>Remove</Button>}</Card>
      <Card className="space-y-4 p-5"><div className="grid gap-4 sm:grid-cols-2"><Input label="First name" value={f.first_name} onChange={(e) => setF({ ...f, first_name: e.target.value })} error={errs.first_name} /><Input label="Last name" value={f.last_name} onChange={(e) => setF({ ...f, last_name: e.target.value })} error={errs.last_name} /></div>
        <Input label="Email" value={user.email} disabled readOnly hint="Email cannot be changed." /><Input label="Phone" type="tel" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} error={errs.phone} />
        <div className="flex justify-end"><Button loading={save.isPending} onClick={submit}>Save profile</Button></div></Card>
      <Card className="p-5"><h3 className="font-semibold">Workspace</h3><p className="mt-1 text-sm text-muted">Currently using the {user.role === 'maker' ? 'Furniture Maker' : 'Home Owner'} experience.</p>
        <Button className="mt-3" variant="secondary" loading={role.isPending} onClick={() => role.mutate(user.role === 'maker' ? 'homeowner' : 'maker')}>Switch to {user.role === 'maker' ? 'Home Owner' : 'Furniture Maker'}</Button></Card>
    </div>
  )
}

function Appearance() {
  const { theme, setTheme } = useUI(); const save = useProfile()
  const pick = (t: 'dark' | 'light') => { setTheme(t); save.mutate({ theme: t }) }
  return (
    <Card className="p-5"><h3 className="font-semibold">Theme</h3><p className="mt-1 text-sm text-muted">Your choice is saved to your profile and applied on all devices.</p>
      <div className="mt-4 grid max-w-md grid-cols-2 gap-3">{([['dark', 'Dark', Moon], ['light', 'Light', Sun]] as const).map(([v, l, I]) => (
        <button key={v} onClick={() => pick(v)} aria-pressed={theme === v} className={clsx('rounded-xl border p-4 text-left transition-colors', theme === v ? 'border-primary bg-primary/10' : 'border-line hover:border-muted/60')}>
          <I size={20} className="text-primary" /><p className="mt-3 font-medium">{l}</p><div className={clsx('mt-3 h-12 rounded-lg border', v === 'dark' ? 'border-slate-700 bg-slate-950' : 'border-slate-200 bg-slate-50')} /></button>))}</div></Card>
  )
}

function Language() {
  const { language, setLanguage } = useUI(); const save = useProfile()
  return (
    <Card className="p-5"><h3 className="font-semibold">Interface language</h3>
      <div className="mt-4 max-w-xs"><Select label="Language" value={language} onChange={(e) => { const l = e.target.value as 'en' | 'uz' | 'ru'; setLanguage(l); save.mutate({ language: l }) }} options={[{ value: 'uz', label: "O'zbekcha" }, { value: 'en', label: 'English' }, { value: 'ru', label: 'Русский' }]} /></div>
      <p className="mt-3 text-xs text-muted">Navigation, sidebar and core actions are translated. Some long-form pages are currently English only.</p></Card>
  )
}

function Notifications() {
  const user = useAuth((s) => s.user)!; const save = useProfile()
  return (
    <Card className="divide-y divide-line">{([['notify_system', 'System notifications', 'In-app alerts about your account and exports.'], ['notify_email', 'Email notifications', 'Account and plan updates by email.']] as const).map(([k, t, d]) => (
      <div key={k} className="flex items-center justify-between gap-4 p-5"><div><p className="font-medium">{t}</p><p className="text-sm text-muted">{d}</p></div><Switch label={t} checked={user[k]} onChange={(v) => save.mutate({ [k]: v })} /></div>))}</Card>
  )
}

function Security() {
  const qc = useQueryClient(); const [f, setF] = useState({ current_password: '', new_password: '', confirm: '' }); const [errs, setErrs] = useState<Record<string, string>>({})
  const sessions = useQuery({ queryKey: ['sessions'], queryFn: async () => (await api.get<{ id: number; created_at: string; expires_at: string }[]>('/users/me/sessions/')).data })
  const pw = useMutation({ mutationFn: () => api.post('/users/me/password/', { current_password: f.current_password, new_password: f.new_password }), onSuccess: () => { toast.success('Password changed'); setF({ current_password: '', new_password: '', confirm: '' }) }, onError: (e) => setErrs(apiError(e).fields) })
  const revoke = useMutation({ mutationFn: (id: number) => api.delete(`/users/me/sessions/${id}/`), onSuccess: () => qc.invalidateQueries({ queryKey: ['sessions'] }) })
  const revokeAll = useMutation({ mutationFn: () => api.delete('/users/me/sessions/'), onSuccess: () => { toast.success('All sessions revoked. You will be signed out when your access token expires.'); qc.invalidateQueries({ queryKey: ['sessions'] }) } })
  const submit = () => { const e: Record<string, string> = {}; if (!f.current_password) e.current_password = 'Required.'; if (f.new_password.length < 8) e.new_password = 'Use at least 8 characters.'; if (f.new_password !== f.confirm) e.confirm = 'Passwords do not match.'; setErrs(e); if (!Object.keys(e).length) pw.mutate() }
  return (
    <div className="space-y-5">
      <Card className="max-w-lg space-y-4 p-5"><h3 className="font-semibold">Change password</h3>
        <Input label="Current password" type="password" autoComplete="current-password" value={f.current_password} onChange={(e) => setF({ ...f, current_password: e.target.value })} error={errs.current_password} />
        <Input label="New password" type="password" autoComplete="new-password" value={f.new_password} onChange={(e) => setF({ ...f, new_password: e.target.value })} error={errs.new_password} />
        <Input label="Confirm new password" type="password" autoComplete="new-password" value={f.confirm} onChange={(e) => setF({ ...f, confirm: e.target.value })} error={errs.confirm} />
        <Button loading={pw.isPending} onClick={submit}>Update password</Button></Card>
      <Card className="p-5"><div className="flex items-center justify-between gap-3"><h3 className="font-semibold">Active sessions</h3><Button size="sm" variant="danger" loading={revokeAll.isPending} onClick={() => revokeAll.mutate()}>Revoke all</Button></div>
        {sessions.isLoading ? <Skeleton className="mt-4 h-20" /> : <ul className="mt-4 divide-y divide-line">{sessions.data?.map((s, i) => <li key={s.id} className="flex items-center justify-between gap-3 py-3 text-sm"><div><p className="font-medium">Signed in {fmtAgo(s.created_at)} {i === 0 && <Badge tone="primary">latest</Badge>}</p><p className="text-xs text-muted">Expires {fmtDate(s.expires_at)}</p></div>
          <Button size="sm" variant="ghost" onClick={() => revoke.mutate(s.id)}>Revoke</Button></li>)}{!sessions.data?.length && <li className="py-4 text-sm text-muted">No active sessions.</li>}</ul>}
        <p className="mt-3 text-xs text-muted">A session is a refresh token. Revoking one prevents it from renewing access.</p></Card>
    </div>
  )
}

function Subscription() {
  const qc = useQueryClient(); const usage = useQuery({ queryKey: ['usage'], queryFn: async () => (await api.get<Usage>('/subscriptions/me/')).data }); const plans = useQuery({ queryKey: ['plans'], queryFn: async () => (await api.get<Plan[]>('/subscriptions/plans/')).data })
  const up = useMutation({ mutationFn: async (slug: string) => (await api.post<{ activated: boolean; detail?: string }>('/subscriptions/upgrade/', { plan: slug })).data, onSuccess: (r) => { toast[r.activated ? 'success' : 'info'](r.activated ? 'Plan changed' : r.detail ?? 'Upgrade requested'); qc.invalidateQueries({ queryKey: ['usage'] }) }, onError: (e) => toast.error(apiError(e).message) })
  const u = usage.data
  if (!u) return <Skeleton className="h-64" />
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-3"><Stat label="Current plan" value={u.plan.name} hint={`$${Number(u.plan.price_usd).toFixed(0)} / month`} /><Stat label="Projects" value={`${u.projects.used} / ${u.projects.limit ?? 'unlimited'}`} /><Stat label="Exports this month" value={`${u.exports_this_month.used} / ${u.exports_this_month.limit ?? 'unlimited'}`} /></div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{plans.data?.map((p) => { const cur = p.slug === u.plan.slug; return (
        <Card key={p.slug} className={clsx('flex flex-col p-4', cur && 'border-primary')}><div className="flex items-center justify-between"><h3 className="font-semibold">{p.name}</h3>{cur && <Badge tone="primary">Current</Badge>}</div>
          <p className="num mt-2 text-2xl font-bold">${Number(p.price_usd).toFixed(0)}<span className="text-xs font-normal text-muted"> /mo</span></p><ul className="mt-3 flex-1 list-disc space-y-1 pl-4 text-xs text-muted">{p.features.map((f) => <li key={f}>{f}</li>)}</ul>
          <Button className="mt-4" size="sm" variant={cur ? 'secondary' : 'primary'} disabled={cur} loading={up.isPending && up.variables === p.slug} onClick={() => up.mutate(p.slug)}>{cur ? 'Current plan' : Number(p.price_usd) === 0 ? 'Switch' : 'Request upgrade'}</Button></Card>) })}</div>
      <p className="text-xs text-muted">Online payment is not integrated yet. Requesting a paid plan creates a pending payment record that an administrator confirms.</p>
      {u.payments.length > 0 && <Card className="p-5"><h3 className="mb-3 font-semibold">Payment records</h3><ul className="divide-y divide-line text-sm">{u.payments.map((p) => <li key={p.id} className="flex items-center justify-between py-2.5"><span>{p.plan} · <span className="num">${p.amount}</span></span><span className="flex items-center gap-3"><span className="text-xs text-muted">{fmtDate(p.created_at)}</span><Badge tone={p.status === 'paid' ? 'success' : p.status === 'pending' ? 'warning' : 'danger'}>{p.status}</Badge></span></li>)}</ul></Card>}
    </div>
  )
}

function Storage() {
  const { data } = useQuery({ queryKey: ['storage'], queryFn: async () => (await api.get<Usage['storage'] & { images_bytes: number; files_bytes: number }>('/users/me/storage/')).data })
  if (!data) return <Skeleton className="h-40" />
  return (
    <Card className="space-y-5 p-5"><div><div className="mb-2 flex justify-between text-sm"><span className="font-medium">{fmtBytes(data.used_bytes)} used</span><span className="num text-muted">of {fmtBytes(data.limit_bytes)} ({data.percent}%)</span></div><Progress value={data.percent} label="Storage used" /></div>
      <div className="grid gap-3 sm:grid-cols-2"><Stat label="Images" value={data.images} hint={fmtBytes(data.images_bytes)} /><Stat label="Files" value={data.files} hint={fmtBytes(data.files_bytes)} /></div>
      <p className="text-xs text-muted">The limit depends on your plan. Delete unused images and files from the Images and Saved files pages to free space.</p></Card>
  )
}

interface TelegramStatus { linked: boolean; username: string; linked_at: string | null }
interface LinkCode { code: string; expires_at: string; ttl_seconds: number }

function Telegram() {
  const qc = useQueryClient()
  const { data, isLoading, isError } = useQuery({ queryKey: ['telegram-status'], queryFn: async () => (await api.get<TelegramStatus>('/telegram/status/')).data })
  const [code, setCode] = useState<LinkCode | null>(null)
  const gen = useMutation({ mutationFn: async () => (await api.post<LinkCode>('/telegram/link-code/')).data, onSuccess: (c) => setCode(c), onError: (e) => toast.error(apiError(e).message) })
  const unlink = useMutation({ mutationFn: () => api.delete('/telegram/status/'), onSuccess: () => { setCode(null); toast.success('Telegram unlinked'); qc.invalidateQueries({ queryKey: ['telegram-status'] }) }, onError: (e) => toast.error(apiError(e).message) })
  if (isLoading) return <Skeleton className="h-40" />
  if (isError || !data) return <Card className="p-5"><p className="text-sm text-danger">Could not load the Telegram status. Try again later.</p></Card>
  return (
    <Card className="space-y-4 p-5">
      <h3 className="font-semibold">Telegram bot</h3>
      {data.linked ? (
        <>
          <p className="text-sm text-muted">Linked{data.username ? ` as @${data.username}` : ''}{data.linked_at ? ` on ${fmtDate(data.linked_at)}` : ''}. You can see orders and projects in the bot.</p>
          <Button variant="secondary" loading={unlink.isPending} onClick={() => { if (window.confirm('Unlink this Telegram account?')) unlink.mutate() }}>Unlink Telegram</Button>
        </>
      ) : (
        <>
          <p className="text-sm text-muted">Open the MEBELCHI AI bot in Telegram, press "Link account" and send the code below. The code works once and expires after a few minutes.</p>
          {code ? (
            <div className="rounded-xl border border-line p-4">
              <p className="text-xs text-muted">Your link code</p>
              <p className="num mt-1 text-2xl font-semibold tracking-widest">{code.code}</p>
              <p className="mt-2 text-xs text-muted">Valid for {Math.round(code.ttl_seconds / 60)} minutes.</p>
            </div>
          ) : null}
          <Button loading={gen.isPending} onClick={() => gen.mutate()}>{code ? 'Get a new code' : 'Get link code'}</Button>
        </>
      )}
    </Card>
  )
}

export default function SettingsPage() {
  const [params, setParams] = useSearchParams(); const initial = (params.get('tab') as Tab) || 'profile'; const [tab, setTab] = useState<Tab>(TABS.some((t) => t[0] === initial) ? initial : 'profile')
  useEffect(() => { const t = params.get('tab') as Tab | null; if (t && TABS.some((x) => x[0] === t)) setTab(t) }, [params])
  return (
    <div className="mx-auto max-w-4xl p-4 sm:p-8"><h1 className="text-2xl font-bold">Settings</h1>
      <div className="mt-5"><Tabs tabs={TABS.map(([id, label, I]) => ({ id, label, icon: <I size={15} /> }))} value={tab} onChange={(t) => { setTab(t); setParams({ tab: t }, { replace: true }) }} /></div>
      <div className="mt-6">{{ profile: <Profile />, appearance: <Appearance />, language: <Language />, notifications: <Notifications />, telegram: <Telegram />, security: <Security />, subscription: <Subscription />, storage: <Storage /> }[tab]}</div></div>
  )
}
