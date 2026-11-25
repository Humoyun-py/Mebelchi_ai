import clsx from 'clsx'
import { AlertTriangle, CheckCircle2, RotateCcw } from 'lucide-react'
import type { Box, ColorGroup, Colors, Consistency } from '../../lib/types'
import { COLOR_GROUPS, DEFAULT_COLORS, GROUP_OF_KIND } from '../../lib/editor'
import { VIEWS, type View } from '../../lib/editor3d'
import { useT } from '../../lib/i18n'
import { Button } from '../ui/Button'

const PALETTE = ['#c9a27a', '#e5e7eb', '#8b6f4e', '#d8c3a5', '#475569', '#1e293b', '#f8fafc', '#7c3f1d']

/** Standard camera views. */
export function ViewBar({ view, onView, onReset }: { view: View; onView: (v: View) => void; onReset: () => void }) {
  const t = useT()
  return (
    <div role="group" aria-label={t('ed.views')} className="inline-flex flex-wrap items-center gap-1 rounded-lg border border-line bg-card p-1">
      {VIEWS.map((v) => (
        <button key={v} type="button" aria-pressed={view === v} onClick={() => onView(v)}
          className={clsx('rounded-md px-3 py-1.5 text-sm font-medium transition-colors', view === v ? 'bg-card2 text-fg ring-1 ring-line' : 'text-muted hover:text-fg')}>{t(`ed.view.${v}`)}</button>))}
      <Button type="button" size="sm" variant="ghost" icon={<RotateCcw size={14} />} onClick={onReset} aria-label={t('ed.reset')}>{t('ed.reset')}</Button>
    </div>
  )
}

export function Swatch({ value, onChange, label }: { value: string; onChange: (c: string) => void; label: string }) {
  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label={label}>
      {PALETTE.map((c) => (
        <button key={c} type="button" onClick={() => onChange(c)} aria-label={`${label} ${c}`} aria-pressed={value.toLowerCase() === c} style={{ background: c }}
          className={clsx('h-7 w-7 rounded-full border-2', value.toLowerCase() === c ? 'border-primary' : 'border-line')} />))}
      <input type="color" value={value} onChange={(e) => onChange(e.target.value)} aria-label={`${label} (custom)`} className="h-7 w-9 cursor-pointer rounded border border-line bg-transparent" />
    </div>
  )
}

/** One colour per group (carcass, fronts, back, handles). A group left alone keeps its default. */
export function ColorsPanel({ colors, onChange }: { colors: Colors; onChange: (c: Colors) => void }) {
  const t = useT()
  return (
    <div className="space-y-3">
      {COLOR_GROUPS.map((g) => (
        <div key={g}>
          <div className="mb-1 flex items-center justify-between"><span className="text-xs font-medium text-muted">{t(`ed.group.${g}`)}</span>
            {colors[g] && <button type="button" className="text-xs text-primary hover:underline" onClick={() => { const { [g]: _drop, ...rest } = colors; onChange(rest) }}>{t('ed.colorReset')}</button>}</div>
          <Swatch label={t(`ed.group.${g}`)} value={colors[g] ?? DEFAULT_COLORS[g]} onChange={(c) => onChange({ ...colors, [g]: c })} />
        </div>))}
    </div>
  )
}

/** Every component of the model as a button, so parts can be chosen without a pointer too. */
export function ComponentList({ boxes, selected, onSelect }: { boxes: Box[]; selected: string | null; onSelect: (name: string | null) => void }) {
  const t = useT()
  return (
    <ul className="max-h-52 space-y-0.5 overflow-y-auto pr-1" aria-label={t('ed.sec.parts')}>
      {boxes.map((b) => (
        <li key={b.name}><button type="button" aria-pressed={selected === b.name} onClick={() => onSelect(selected === b.name ? null : b.name)}
          className={clsx('flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-sm', selected === b.name ? 'bg-primary/15 text-fg ring-1 ring-primary/40' : 'text-muted hover:bg-card2 hover:text-fg')}>
          <span className="h-3 w-3 shrink-0 rounded-sm border border-line" style={{ background: b.color }} aria-hidden /><span className="truncate">{b.name}</span></button></li>))}
    </ul>
  )
}

export function ComponentProperties({ box, colors, onColor }: { box: Box | null; colors: Colors; onColor: (g: ColorGroup, c: string) => void }) {
  const t = useT()
  if (!box) return <p className="text-xs text-muted">{t('ed.pickHint')}</p>
  const group = GROUP_OF_KIND[box.kind] ?? 'carcass'
  const rows: [string, string][] = [[t('ed.prop.name'), box.name], [t('ed.prop.type'), t(`ed.kind.${box.kind}`)], [t('f.width'), `${box.sx} mm`], [t('f.height'), `${box.sy} mm`], [t('f.depth'), `${box.sz} mm`],
    [t('ed.prop.position'), `${box.x}, ${box.y}, ${box.z}`]]
  return (
    <div className="space-y-3" data-testid="selected-part">
      <dl className="space-y-1.5 text-sm">{rows.map(([k, v]) => <div key={k} className="flex justify-between gap-3"><dt className="text-muted">{k}</dt><dd className="num text-right">{v}</dd></div>)}</dl>
      <div><p className="mb-1 text-xs font-medium text-muted">{t('ed.groupColor').replace('{group}', t(`ed.group.${group}`))}</p>
        <Swatch label={t(`ed.group.${group}`)} value={colors[group] ?? DEFAULT_COLORS[group]} onChange={(c) => onColor(group, c)} /></div>
    </div>
  )
}

/** The proof that the drawn model is the calculated cabinet (checked by the server on every preview). */
export function ConsistencyBadge({ c }: { c: Consistency | undefined }) {
  const t = useT()
  if (!c) return null
  return (
    <div role="status" className={clsx('flex items-start gap-2 rounded-lg border p-3 text-xs', c.valid ? 'border-success/30 bg-success/10 text-success' : 'border-danger/30 bg-danger/10 text-danger')}>
      {c.valid ? <CheckCircle2 size={15} className="mt-0.5 shrink-0" /> : <AlertTriangle size={15} className="mt-0.5 shrink-0" />}
      <div><p className="font-medium">{c.valid ? t('ed.check.ok') : t('ed.check.bad')}</p>
        {c.valid ? <p className="mt-0.5 text-muted">{t('ed.check.detail')}</p> : <ul className="mt-1 list-disc space-y-0.5 pl-4">{c.problems.map((p) => <li key={p}>{p}</li>)}</ul>}</div>
    </div>
  )
}
