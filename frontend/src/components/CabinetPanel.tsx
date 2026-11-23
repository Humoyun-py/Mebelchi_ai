import clsx from 'clsx'
import type { Box, CabinetInput, CalcPart } from '../lib/types'
import { NumberField } from './ui/Field'
import { DataTable, type Column } from './ui/Misc'
import { useMeta } from '../hooks/queries'
import { useT } from '../lib/i18n'

export const DEFAULT_INPUT: CabinetInput = { width: 800, height: 2000, depth: 400, thickness: 18, shelves: 3, doors: 2, drawers: 0 }
const FALLBACK = { width: [200, 4000], height: [200, 3000], depth: [150, 1000], thickness: [8, 40], shelves: [0, 20], doors: [0, 6], drawers: [0, 10] } as Record<string, number[]>
type LimKey = 'width' | 'height' | 'depth' | 'thickness' | 'shelves' | 'doors' | 'drawers'

export function CabinetForm({ value, onChange, errors = {} }: { value: CabinetInput; onChange: (v: CabinetInput) => void; errors?: Record<string, string> }) {
  const t = useT(); const { data: meta } = useMeta(); const LIM = meta?.limits ?? FALLBACK
  const set = (k: keyof CabinetInput) => (n: number) => onChange({ ...value, [k]: n })
  const f = (k: LimKey, label: string, unit?: string, step = 1) => (
    <NumberField label={label} unit={unit} step={step} min={LIM[k][0]} max={LIM[k][1]} value={value[k]} onChange={set(k)} error={errors[k] ?? (!Number.isFinite(value[k]) ? t('f.required') : undefined)} />)
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">{f('width', t('f.width'), 'mm')}{f('height', t('f.height'), 'mm')}{f('depth', t('f.depth'), 'mm')}{f('thickness', t('f.thickness'), 'mm')}</div>
      <div className="grid grid-cols-3 gap-3">{f('shelves', t('f.shelves'))}{f('doors', t('f.doors'))}{f('drawers', t('f.drawers'))}</div>
    </div>
  )
}

export function PartsTable({ parts }: { parts: CalcPart[] }) {
  const t = useT(); const partName = (n: string) => { const k = 'part.' + n; const v = t(k); return v === k ? n : v }
  const rows = parts.map((p, i) => ({ ...p, id: i }))
  const cols: Column<(typeof rows)[number]>[] = [
    { key: 'n', header: t('f.part'), className: 'whitespace-nowrap', render: (p) => <span className="font-medium">{partName(p.name)}</span> },
    { key: 'w', header: t('f.width'), className: 'num text-right', render: (p) => p.width },
    { key: 'h', header: t('f.height'), className: 'num text-right', render: (p) => p.height },
    { key: 't', header: t('f.thick'), className: 'num text-right', render: (p) => p.thickness },
    { key: 'q', header: t('f.qty'), className: 'num text-right', render: (p) => p.quantity },
    { key: 'm', header: t('f.material'), className: 'hidden sm:table-cell', render: (p) => p.material },
    { key: 'e', header: t('calc.edge'), className: 'hidden md:table-cell text-muted whitespace-nowrap', render: (p) => p.edge_note || '-' },
  ]
  return <DataTable columns={cols} rows={rows} />
}

/** Front elevation (x/y) of the parametric model. Draws back-to-front; clicking selects a component. */
export function FrontView({ boxes, dims, selected, onSelect }: { boxes: Box[]; dims: { width: number; height: number; depth: number }; selected?: string | null; onSelect?: (b: Box) => void }) {
  const pad = 70, W = dims.width, H = dims.height
  const ordered = [...boxes].sort((a, b) => a.z + a.sz - (b.z + b.sz))
  return (
    <svg viewBox={`${-pad} ${-pad} ${W + pad * 2} ${H + pad * 2}`} className="h-full max-h-[460px] w-full" role="img" aria-label={`Front view, ${W} by ${H} millimetres`}>
      <g transform={`translate(0 ${H}) scale(1 -1)`}>
        {ordered.map((b, i) => (
          <rect key={`${b.name}-${i}`} x={b.x} y={b.y} width={b.sx} height={b.sy} fill={b.color} fillOpacity={b.kind === 'back' ? 0.35 : 0.9}
            stroke={selected === b.name ? 'var(--primary)' : '#0f172a'} strokeWidth={selected === b.name ? 5 : 1.5} onClick={() => onSelect?.(b)} className={onSelect ? 'cursor-pointer' : ''}>
            <title>{b.name}</title></rect>))}
      </g>
      <g stroke="#60a5fa" strokeWidth={2} fill="#60a5fa" fontSize={Math.max(22, W / 28)} fontFamily="Geist Variable, sans-serif">
        <line x1={0} y1={H + 40} x2={W} y2={H + 40} /><text x={W / 2} y={H + 40 + Math.max(22, W / 28) + 4} textAnchor="middle" stroke="none">{W} mm</text>
        <line x1={W + 40} y1={0} x2={W + 40} y2={H} /><text x={W + 48} y={H / 2} stroke="none" transform={`rotate(90 ${W + 48} ${H / 2})`} textAnchor="middle">{H} mm</text>
      </g>
    </svg>
  )
}

export const Swatches = ({ value, onChange }: { value: string; onChange: (c: string) => void }) => (
  <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Color">
    {['#c9a27a', '#e5e7eb', '#8b6f4e', '#d8c3a5', '#475569', '#1e293b', '#f8fafc'].map((c) => (
      <button key={c} type="button" onClick={() => onChange(c)} aria-label={`Color ${c}`} aria-pressed={value === c} style={{ background: c }}
        className={clsx('h-7 w-7 rounded-full border-2', value === c ? 'border-primary' : 'border-line')} />))}
    <input type="color" value={value} onChange={(e) => onChange(e.target.value)} aria-label="Custom color" className="h-7 w-9 cursor-pointer rounded border border-line bg-transparent" />
  </div>
)
