import { useState } from 'react'
import { ImagePlus } from 'lucide-react'
import clsx from 'clsx'
import { api, apiError } from '../../lib/api'
import type { GalleryImage } from '../../lib/types'
import { defaultOpenings, type Field, type Question, type RoomFlow, type RoomOpening, type RoomSize, WALLS, type Wall } from '../../lib/room'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { NumberField, Select } from '../ui/Field'
import { FileUploader } from '../ui/FileUploader'
import { toast } from '../ui/Toast'
import { useL, useT } from '../../lib/i18n'

type Submit = (step: string, value: unknown) => Promise<unknown>
interface Props { flow: RoomFlow; submit: Submit; busy: boolean; error: { message: string; fields: Record<string, string> } | null; onBack: () => void }

function Choice({ q, submit, busy }: { q: Question; submit: Submit; busy: boolean }) {
  const L = useL(); const cur = q.value as string | undefined
  return (
    <div className="grid gap-3 sm:grid-cols-2" role="radiogroup" aria-label={L(q.title)}>
      {q.options?.map((o) => (
        <button key={o.id} type="button" role="radio" aria-checked={cur === o.id} disabled={busy} onClick={() => submit(q.step, o.id)}
          className={clsx('rounded-[14px] border p-4 text-left transition-colors hover:border-primary disabled:opacity-60', cur === o.id ? 'border-primary bg-primary/10' : 'border-line bg-card2')}>
          <span className="flex items-center gap-3">
            {o.furniture && o.wall && <span aria-hidden className="flex shrink-0"><span className="h-7 w-7 rounded-l-md border border-line" style={{ background: o.wall }} /><span className="h-7 w-7 rounded-r-md border border-line" style={{ background: o.furniture }} /></span>}
            <span><span className="block font-medium">{L(o.label)}</span>{o.text && <span className="mt-0.5 block text-xs text-muted">{L(o.text)}</span>}</span>
          </span>
        </button>
      ))}
    </div>
  )
}

function Photo({ q, submit, busy }: { q: Question; submit: Submit; busy: boolean }) {
  const t = useT(); const [up, setUp] = useState(false); const [name, setName] = useState('')
  const upload = async (files: File[]) => {
    setUp(true)
    try { const fd = new FormData(); fd.append('image', files[0]); fd.append('source', 'room'); const img = (await api.post<GalleryImage>('/gallery/', fd)).data; setName(img.name); await submit(q.step, { image_id: img.id }) }
    catch (e) { toast.error(apiError(e).message) } finally { setUp(false) }
  }
  return (
    <div className="space-y-4">
      <FileUploader accept="image/png,image/jpeg,image/webp" maxMB={10} onFiles={upload} disabled={busy || up} label={t('room.photoUpload')} />
      {name && <p className="flex items-center gap-2 text-sm text-muted"><ImagePlus size={15} aria-hidden />{name}</p>}
      <Button variant="secondary" disabled={busy || up} onClick={() => submit(q.step, { skip: true })}>{t('room.skip')}</Button>
    </div>
  )
}

function Group({ q, submit, busy, error }: { q: Question } & Omit<Props, 'flow' | 'onBack'>) {
  const L = useL(); const t = useT()
  const prev = (q.value ?? {}) as Record<string, unknown>
  const initial = (f: Field) => f.type === 'multi' ? ((prev[f.key] as string[] | undefined) ?? []) : Number(prev[f.key] ?? f.default ?? f.min ?? 0)
  const [vals, setVals] = useState<Record<string, number | string[]>>(() => Object.fromEntries((q.fields ?? []).map((f) => [f.key, initial(f)])))
  const set = (k: string, v: number | string[]) => setVals((x) => ({ ...x, [k]: v }))
  return (
    <form noValidate onSubmit={(e) => { e.preventDefault(); submit(q.step, vals) }} className="space-y-5">
      {(q.fields ?? []).map((f) => f.type === 'number' ? (
        <div key={f.key} className="max-w-xs"><NumberField label={L(f.label)} value={vals[f.key] as number} onChange={(n) => set(f.key, n)} min={f.min} max={f.max} unit={q.unit} error={error?.fields[f.key]} /></div>
      ) : (
        <fieldset key={f.key}>
          <legend className="mb-2 text-xs font-medium text-muted">{L(f.label)}</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {f.options?.map((o) => { const list = vals[f.key] as string[]; const on = list.includes(o.id)
              return (
                <label key={o.id} className={clsx('flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm', on ? 'border-primary bg-primary/10' : 'border-line bg-card2')}>
                  <input type="checkbox" checked={on} onChange={() => set(f.key, on ? list.filter((s) => s !== o.id) : [...list, o.id])} className="accent-[var(--primary)]" />{L(o.label)}
                </label>) })}
          </div>
          {error?.fields[f.key] && <p role="alert" className="mt-1 text-xs text-danger">{error.fields[f.key]}</p>}
        </fieldset>
      ))}
      <Button type="submit" loading={busy}>{t('room.next')}</Button>
    </form>
  )
}

function Openings({ q, submit, busy, error }: { q: Question } & Omit<Props, 'flow' | 'onBack'>) {
  const L = useL(); const t = useT()
  const room = (q.room ?? { width: 4000, length: 3000, height: 2700 }) as RoomSize
  const [rows, setRows] = useState<RoomOpening[]>(() => (Array.isArray(q.value) && q.value.length ? (q.value as RoomOpening[]) : defaultOpenings(q.required ?? { doors: 0, windows: 0 }, room, q.limits?.edge_margin ?? 100, q.limits?.gap ?? 100, q.walls?.map((w) => w.id))))
  const upd = (i: number, patch: Partial<RoomOpening>) => setRows((r) => r.map((o, j) => (j === i ? { ...o, ...patch } : o)))
  const nth = (i: number) => rows.slice(0, i + 1).filter((x) => x.type === rows[i].type).length
  const margin = q.limits?.edge_margin ?? 100
  // Checked here first, in the user's language and per opening; the server repeats the same rule (and stays the authority).
  const gap = q.limits?.gap ?? 100
  const problem = (o: RoomOpening): string | null => {
    const len = q.wall_lengths?.[o.wall]
    if (len == null) return null
    const clash = rows.some((x) => x !== o && x.wall === o.wall && o.offset < x.offset + x.width + gap && x.offset < o.offset + o.width + gap && (x.offset < o.offset || (x.offset === o.offset && rows.indexOf(x) < rows.indexOf(o))))
    if (clash) return t('room.err.overlap').replace('{gap}', String(gap))
    if (o.offset < margin) return t('room.err.offsetMin').replace('{m}', String(margin))
    if (o.offset + o.width > len - margin) {
      const room = len - margin - o.offset
      return room >= 300 ? t('room.err.fitWidth').replace('{max}', String(room)).replace('{len}', String(len)) : t('room.err.fitOffset').replace('{len}', String(len)).replace('{m}', String(margin))
    }
    return null
  }
  const serverFor = (i: number) => Object.entries(error?.fields ?? {}).filter(([k]) => k.startsWith(`openings.${i}.`)).map(([, v]) => v)[0]
  const firstBad = rows.findIndex((o) => problem(o))
  return (
    <form noValidate onSubmit={(e) => { e.preventDefault(); if (firstBad >= 0) return; submit(q.step, rows) }} className="space-y-4">
      {rows.map((o, i) => {
        const n = nth(i); const lim = o.type === 'door' ? q.limits?.door : q.limits?.window; const len = q.wall_lengths?.[o.wall]
        return (
          <fieldset key={i} className="rounded-[14px] border border-line bg-card2 p-4">
            <legend className="px-1 text-sm font-medium">{t(o.type === 'door' ? 'room.door' : 'room.window').replace('{n}', String(n))}</legend>
            <div className="grid gap-3 sm:grid-cols-3">
              <Select label={t('room.wall')} value={o.wall} onChange={(e) => upd(i, { wall: e.target.value as Wall })} options={(q.walls ?? WALLS.map((id) => ({ id, label: { en: id } }))).map((x) => ({ value: x.id, label: L(x.label) }))} />
              <NumberField label={t('room.offset')} value={o.offset} onChange={(v) => upd(i, { offset: v })} min={0} max={len} unit="mm" />
              <NumberField label={t('room.width')} value={o.width} onChange={(v) => upd(i, { width: v })} min={lim?.width[0]} max={lim?.width[1]} unit="mm" />
              <NumberField label={t('room.height')} value={o.height} onChange={(v) => upd(i, { height: v })} min={lim?.height[0]} max={lim?.height[1]} unit="mm" />
              {o.type === 'window' && <NumberField label={t('room.sill')} value={o.sill} onChange={(v) => upd(i, { sill: v })} min={0} max={q.limits?.window.sill[1]} unit="mm" />}
            </div>
            {(problem(o) ?? serverFor(i)) && <p role="alert" className="mt-3 text-sm text-danger">{problem(o) ?? serverFor(i)}</p>}
          </fieldset>
        )
      })}
      {error && !Object.keys(error.fields).some((k) => k.startsWith('openings.')) && <p role="alert" className="text-sm text-danger">{Object.values(error.fields)[0] ?? error.message}</p>}
      {firstBad >= 0 && <p className="text-sm text-muted">{t('room.err.fixAbove')}</p>}
      <Button type="submit" loading={busy} disabled={firstBad >= 0}>{t('room.next')}</Button>
    </form>
  )
}

/** Renders the current question of the server-side conversation. Questions, options, limits and texts all come from the API,
 *  so the web app and the Telegram bot cannot drift apart. */
export function Wizard({ flow, submit, busy, error, onBack }: Props) {
  const L = useL(); const t = useT(); const q = flow.question
  const common = { q, submit, busy, error }
  return (
    <Card className="mx-auto max-w-2xl p-6">
      <p className="text-xs font-medium uppercase tracking-wide text-muted">{t('room.step').replace('{n}', String(q.index)).replace('{m}', String(q.total))}</p>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-line" role="progressbar" aria-valuemin={1} aria-valuemax={q.total} aria-valuenow={q.index}><div className="h-full rounded-full bg-primary transition-all" style={{ width: `${(q.index / q.total) * 100}%` }} /></div>
      <h2 className="mt-5 text-xl font-semibold">{L(q.title)}</h2>
      <p className="mb-5 mt-1 text-sm text-muted">{L(q.prompt)}</p>
      {q.kind === 'choice' && <Choice q={q} submit={submit} busy={busy} />}
      {q.kind === 'photo' && <Photo q={q} submit={submit} busy={busy} />}
      {q.kind === 'number_group' && <Group key={q.step} {...common} />}
      {q.kind === 'openings' && <Openings key={q.step} {...common} />}
      {error && q.kind !== 'openings' && q.kind !== 'number_group' && <p role="alert" className="mt-3 text-sm text-danger">{error.message}</p>}
      {q.can_back && <div className="mt-6 border-t border-line pt-4"><Button variant="ghost" onClick={onBack} disabled={busy}>{t('room.back')}</Button></div>}
    </Card>
  )
}
