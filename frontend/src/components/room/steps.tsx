import { useMemo, useState } from 'react'
import { ImagePlus, Minus, Plus } from 'lucide-react'
import clsx from 'clsx'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { FileUploader } from '../ui/FileUploader'
import { NumberField, Select } from '../ui/Field'
import { useL, useT } from '../../lib/i18n'
import { defaultOpening, fill, wallLength, type Descriptor, type Opening, type Room, type Wall } from '../../lib/roomFlow'

type Errors = Record<string, string>

export function ChoiceStep({ d, onPick, busy }: { d: Descriptor; onPick: (id: string) => void; busy: boolean }) {
  const L = useL()
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {d.options?.map((o) => (
        <button key={o.id} type="button" disabled={busy} onClick={() => onPick(o.id)} aria-pressed={d.value === o.id}
          className={clsx('rounded-xl border p-4 text-left transition-colors disabled:opacity-60', d.value === o.id ? 'border-primary bg-primary/10' : 'border-line bg-card hover:border-muted/60')}>
          <span className="flex items-center justify-between gap-3"><span className="font-medium">{L(o.label)}</span>
            {o.wall && o.furniture && <span className="flex gap-1" aria-hidden><span className="h-4 w-4 rounded-full border border-line" style={{ background: o.wall }} /><span className="h-4 w-4 rounded-full border border-line" style={{ background: o.furniture }} /></span>}</span>
          {o.text && <span className="mt-1 block text-sm text-muted">{L(o.text)}</span>}
        </button>))}
    </div>
  )
}

export function PhotoStep({ onUpload, onSkip, busy }: { onUpload: (f: File) => void; onSkip: () => void; busy: boolean }) {
  const t = useT()
  return (
    <div className="space-y-4">
      <FileUploader accept="image/png,image/jpeg,image/webp" maxMB={10} onFiles={(f) => onUpload(f[0])} disabled={busy} label={busy ? t('rf.uploading') : t('rf.upload')} />
      <Button variant="secondary" icon={<ImagePlus size={16} />} disabled={busy} onClick={onSkip}>{t('rf.skip')}</Button>
    </div>
  )
}

const FIELD_DEFAULTS: Record<string, number> = { width: 4000, length: 3000, height: 2700 }

/** Number fields and a furniture picker with quantities. Server messages appear next to the field they belong to. */
export function NumberGroupStep({ d, onSubmit, busy, errors }: { d: Descriptor; onSubmit: (value: Record<string, unknown>) => void; busy: boolean; errors: Errors }) {
  const L = useL(), t = useT()
  const saved = (d.value ?? {}) as Record<string, unknown>
  const [nums, setNums] = useState<Record<string, number>>(() => Object.fromEntries((d.fields ?? []).filter((f) => f.type === 'number')
    .map((f) => [f.key, typeof saved[f.key] === 'number' ? (saved[f.key] as number) : (f.default ?? FIELD_DEFAULTS[f.key] ?? f.min ?? 0)])))
  const [qty, setQty] = useState<Record<string, number>>(() => {
    const counts: Record<string, number> = {}
    for (const s of (saved.furniture as string[] | undefined) ?? []) counts[s] = (counts[s] ?? 0) + 1
    return counts
  })
  const bad = Object.values(nums).some((n) => !Number.isFinite(n))
  const submit = () => onSubmit({ ...nums, ...((d.fields ?? []).some((f) => f.type === 'multi') ? { furniture: Object.entries(qty).flatMap(([slug, n]) => Array(n).fill(slug)) } : {}) })
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2">
        {d.fields?.filter((f) => f.type === 'number').map((f) => (
          <NumberField key={f.key} label={L(f.label)} unit={d.unit} min={f.min} max={f.max} value={nums[f.key]} onChange={(n) => setNums({ ...nums, [f.key]: n })}
            error={errors[f.key] ?? (!Number.isFinite(nums[f.key]) ? '-' : undefined)} />))}
      </div>
      {d.fields?.filter((f) => f.type === 'multi').map((f) => (
        <fieldset key={f.key}><legend className="mb-2 text-sm font-medium">{L(f.label)}</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {f.options?.map((o) => (
              <Card key={o.id} className="flex items-center justify-between gap-3 p-3"><span className="text-sm">{L(o.label)}</span>
                <span className="flex items-center gap-2" role="group" aria-label={`${L(o.label)}: ${t('rf.qty')}`}>
                  <Button size="sm" variant="secondary" aria-label={`${L(o.label)} -`} disabled={!qty[o.id]} onClick={() => setQty({ ...qty, [o.id]: (qty[o.id] ?? 0) - 1 })} icon={<Minus size={14} />} />
                  <span className="num w-5 text-center text-sm" aria-live="polite">{qty[o.id] ?? 0}</span>
                  <Button size="sm" variant="secondary" aria-label={`${L(o.label)} +`} onClick={() => setQty({ ...qty, [o.id]: (qty[o.id] ?? 0) + 1 })} icon={<Plus size={14} />} />
                </span></Card>))}
          </div>
          {errors[f.key] && <p role="alert" className="mt-1 text-xs text-danger">{errors[f.key]}</p>}
        </fieldset>))}
      <Button loading={busy} disabled={bad} onClick={submit}>{t('rf.next')}</Button>
    </div>
  )
}

export function OpeningsStep({ d, onSubmit, busy, errors }: { d: Descriptor; onSubmit: (value: Opening[]) => void; busy: boolean; errors: Errors }) {
  const L = useL(), t = useT()
  const room = d.room as Room
  const lengths = d.wall_lengths
  const initial = useMemo<Opening[]>(() => {
    if (Array.isArray(d.value) && d.value.length) return d.value as Opening[]
    const rows: Opening[] = []
    for (let i = 0; i < (d.required?.doors ?? 0); i++) rows.push(defaultOpening('door', i % 2 ? 'south' : 'north', room))
    for (let i = 0; i < (d.required?.windows ?? 0); i++) rows.push(defaultOpening('window', (['east', 'west', 'north', 'south'] as Wall[])[i % 4], room))
    return rows
  }, [d, room])
  const [rows, setRows] = useState<Opening[]>(initial)
  const set = (i: number, patch: Partial<Opening>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)))
  const bad = rows.some((r) => [r.offset, r.width, r.height, r.sill].some((n) => !Number.isFinite(n)))
  return (
    <div className="space-y-4">
      {rows.map((r, i) => {
        const nth = rows.slice(0, i + 1).filter((x) => x.type === r.type).length
        const err = (f: string) => errors[`openings.${i}.${f}`]
        return (
          <Card key={i} className="space-y-3 p-4" data-testid={`opening-${i}`}>
            <h3 className="font-medium">{fill(t(r.type === 'door' ? 'rf.door' : 'rf.window'), { n: nth })}</h3>
            <div className="grid gap-3 sm:grid-cols-2">
              <Select label={t('rf.wall')} value={r.wall} onChange={(e) => set(i, { wall: e.target.value as Wall })} options={(d.walls ?? []).map((w) => ({ value: w.id, label: L(w.label) }))} />
              <NumberField label={t('rf.offset')} unit="mm" value={r.offset} onChange={(n) => set(i, { offset: n })} error={err('offset')} />
              <NumberField label={t('rf.width')} unit="mm" value={r.width} onChange={(n) => set(i, { width: n })} error={err('width')} />
              <NumberField label={t('rf.height')} unit="mm" value={r.height} onChange={(n) => set(i, { height: n })} error={err('height')} />
              {r.type === 'window' && <NumberField label={t('rf.sill')} unit="mm" value={r.sill} onChange={(n) => set(i, { sill: n })} error={err('sill')} />}
            </div>
            {lengths && <p className="text-xs text-muted">{fill(t('rf.wallLength'), { n: wallLength(room, r.wall) })}</p>}
            {(err('type') || err('wall')) && <p role="alert" className="text-xs text-danger">{err('type') ?? err('wall')}</p>}
          </Card>)
      })}
      {errors.openings && <p role="alert" className="text-sm text-danger">{errors.openings}</p>}
      <Button loading={busy} disabled={bad} onClick={() => onSubmit(rows.map(({ id: _id, ...o }) => o))}>{t('rf.next')}</Button>
    </div>
  )
}
