import { useRef, useState } from 'react'
import { ImagePlus, Trash2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { api, apiError } from '../../lib/api'
import { useT } from '../../lib/i18n'
import type { Workshop } from '../../lib/types'
import { useAction } from '../../hooks/workshops'
import { toast } from '../ui/Toast'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { Input, Select, Textarea } from '../ui/Field'
import { ConfirmDialog } from '../ui/Modal'

export function SettingsTab({ ws, writable }: { ws: Workshop; writable: boolean }) {
  const t = useT(); const nav = useNavigate(); const file = useRef<HTMLInputElement>(null)
  const [f, setF] = useState({ name: ws.name, description: ws.description, phone: ws.phone, email: ws.email, address: ws.address }); const [errs, setErrs] = useState<Record<string, string>>({}); const [del, setDel] = useState(false)
  const suspended = ws.status === 'suspended'
  const dirty = (Object.keys(f) as (keyof typeof f)[]).some((k) => f[k] !== ws[k])
  const save = useAction((b: Record<string, string>) => api.patch(`/workshops/${ws.id}/`, b), { ok: t('ws.saved'), onError: (e) => setErrs({ ...apiError(e).fields, _: apiError(e).message }) })
  const status = useAction((s: string) => api.patch(`/workshops/${ws.id}/`, { status: s }), { ok: t('ws.saved') })
  const logo = useAction((fl: File | null) => { if (!fl) return api.delete(`/workshops/${ws.id}/logo/`); const fd = new FormData(); fd.append('logo', fl); return api.post(`/workshops/${ws.id}/logo/`, fd) }, { ok: t('ws.saved') })
  const remove = useAction(() => api.delete(`/workshops/${ws.id}/`), { ok: t('ws.deleted'), onSuccess: () => nav('/app/workshops'), onError: (e) => { toast.error(apiError(e).message); setDel(false) } })
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => { setF({ ...f, [k]: e.target.value }); setErrs({}) }
  const off = suspended || (!writable && ws.status !== 'inactive')
  return (
    <div className="max-w-2xl space-y-5">
      <Card className="space-y-4 p-5">
        <div className="flex items-center gap-4">
          <div className="flex h-16 w-16 items-center justify-center overflow-hidden rounded-xl bg-card2 text-muted">{ws.logo_url ? <img src={ws.logo_url} alt="" className="h-full w-full object-cover" /> : <ImagePlus size={22} />}</div>
          <div className="flex flex-wrap gap-2">
            <input ref={file} type="file" accept="image/png,image/jpeg,image/webp" hidden aria-label={t('ws.logo')} onChange={(e) => { const fl = e.target.files?.[0]; if (fl) logo.mutate(fl); e.target.value = '' }} />
            <Button size="sm" variant="secondary" loading={logo.isPending} disabled={off || !writable} onClick={() => file.current?.click()}>{t('ws.logoUpload')}</Button>
            {ws.logo_url && <Button size="sm" variant="ghost" disabled={logo.isPending || !writable} onClick={() => logo.mutate(null)}>{t('ws.logoRemove')}</Button>}</div></div>
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); if (dirty) { setErrs({}); save.mutate(f) } }}>
          <Input label={t('ws.name')} value={f.name} maxLength={120} onChange={set('name')} error={errs.name} disabled={off} />
          <Textarea label={t('ws.description')} value={f.description} onChange={set('description')} error={errs.description} disabled={off} />
          <div className="grid gap-4 sm:grid-cols-2"><Input label={t('ws.phone')} value={f.phone} maxLength={32} onChange={set('phone')} error={errs.phone} disabled={off} /><Input label={t('ws.email')} type="email" value={f.email} onChange={set('email')} error={errs.email} disabled={off} /></div>
          <Input label={t('ws.address')} value={f.address} maxLength={255} onChange={set('address')} error={errs.address} disabled={off} />
          {errs._ && !Object.keys(errs).some((k) => k !== '_' && errs[k]) && <p role="alert" className="text-sm text-danger">{errs._}</p>}
          <Button type="submit" loading={save.isPending} disabled={!dirty || off || f.name.trim().length < 2}>{t('common.save')}</Button>
        </form>
      </Card>
      <Card className="space-y-3 p-5"><h3 className="font-semibold">{t('ws.statusTitle')}</h3><p className="text-sm text-muted">{suspended ? t('ws.suspendedNote') : t('ws.statusNote')}</p>
        {!suspended && <div className="w-48"><Select label={t('ord.status')} value={ws.status} disabled={status.isPending} onChange={(e) => status.mutate(e.target.value)} options={[{ value: 'active', label: t('ws.st.active') }, { value: 'inactive', label: t('ws.st.inactive') }]} /></div>}</Card>
      <Card className="space-y-3 border-danger/30 p-5"><h3 className="font-semibold text-danger">{t('ws.dangerTitle')}</h3><p className="text-sm text-muted">{t('ws.deleteNote')}</p>
        <Button variant="danger" icon={<Trash2 size={15} />} disabled={suspended} onClick={() => setDel(true)}>{t('ws.delete')}</Button></Card>
      <ConfirmDialog open={del} onClose={() => setDel(false)} title={t('ws.deleteTitle')} message={t('ws.deleteMsg')} cancelLabel={t('common.cancel')} loading={remove.isPending} onConfirm={() => remove.mutate(undefined)} />
    </div>
  )
}
