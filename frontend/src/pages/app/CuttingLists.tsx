import { useEffect, useId, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Calculator, FileSpreadsheet, FileText, Layers, Plus, Save, Scissors, Trash2 } from 'lucide-react'
import { api, apiError, downloadBlob } from '../../lib/api'
import { fmtAgo } from '../../lib/format'
import type { CuttingList, CuttingPart, OptGroup, OptRun, Page } from '../../lib/types'
import { Button } from '../../components/ui/Button'
import { Card, HoverCard } from '../../components/ui/Card'
import { Input, NumberField } from '../../components/ui/Field'
import { ConfirmDialog } from '../../components/ui/Modal'
import { Breadcrumbs, EmptyState, ErrorState, Progress, Skeleton, Stat } from '../../components/ui/Misc'
import { toast } from '../../components/ui/Toast'
import { PanelSection, RightPanel } from '../../layouts/RightPanel'

const FALLBACK = ['#3b82f6', '#22c55e', '#f59e0b', '#a855f7', '#06b6d4', '#ef4444', '#84cc16', '#ec4899']

/** One sheet drawn to scale: offcut hatching, numbered parts, rulers. Colors and legend come from the backend. */
function SheetSvg({ group, idx }: { group: OptGroup; idx: number }) {
  const uid = useId().replace(/:/g, ''); const { sheet } = group.result; const s = group.result.sheets[idx]; const trim = sheet.trim
  const L = sheet.length, W = sheet.width, m = Math.max(L, W) * 0.05, fs = Math.max(L, W) / 52
  const names = Array.from(new Set(group.result.sheets.flatMap((x) => x.placements.map((p) => p.name))))
  const colorOf = (p: { name: string; color?: string }) => p.color ?? FALLBACK[names.indexOf(p.name) % FALLBACK.length]
  const tone = s.utilization_pct >= 70 ? 'text-success' : s.utilization_pct >= 45 ? 'text-warning' : 'text-danger'
  return (
    <figure className="overflow-hidden rounded-2xl border border-line bg-card shadow-sm">
      <figcaption className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
        <span className="flex items-center gap-2 text-sm font-semibold"><span className="num flex h-6 min-w-6 items-center justify-center rounded-md bg-primary/15 px-1.5 text-xs text-primary">{s.index}</span>{group.key}<span className="text-xs font-normal text-muted">/ {group.result.sheets.length}</span></span>
        <span className="flex items-center gap-3"><span className="hidden w-28 sm:block"><Progress value={s.utilization_pct} tone={s.utilization_pct >= 70 ? 'success' : 'warning'} label="Sheet utilization" /></span><span className={`num text-sm font-semibold ${tone}`}>{s.utilization_pct}%</span></span>
      </figcaption>
      <div className="p-3">
        <svg viewBox={`${-m} ${-m} ${L + m * 1.4} ${W + m * 1.4}`} className="w-full" role="img" aria-label={`Cutting layout sheet ${s.index}, ${s.placements.length} pieces, ${s.utilization_pct}% used`}>
          <defs>
            <pattern id={`h${uid}`} width={fs * 1.6} height={fs * 1.6} patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2={fs * 1.6} stroke="var(--muted)" strokeOpacity="0.22" strokeWidth={fs * 0.12} /></pattern>
            <linearGradient id={`w${uid}`} x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stopColor="var(--card2)" /><stop offset="100%" stopColor="var(--card)" /></linearGradient>
            <filter id={`s${uid}`} x="-5%" y="-5%" width="110%" height="115%"><feDropShadow dx="0" dy={fs * 0.12} stdDeviation={fs * 0.15} floodOpacity="0.35" /></filter>
          </defs>
          <g stroke="var(--muted)" strokeWidth={fs * 0.1} fill="var(--muted)" fontSize={fs * 1.1} fontFamily="Geist Variable, sans-serif">
            <line x1={0} y1={-m * 0.45} x2={L} y2={-m * 0.45} /><line x1={0} y1={-m * 0.6} x2={0} y2={-m * 0.3} /><line x1={L} y1={-m * 0.6} x2={L} y2={-m * 0.3} />
            <text x={L / 2} y={-m * 0.55} textAnchor="middle" stroke="none">{L} mm</text>
            <line x1={-m * 0.45} y1={0} x2={-m * 0.45} y2={W} /><line x1={-m * 0.6} y1={0} x2={-m * 0.3} y2={0} /><line x1={-m * 0.6} y1={W} x2={-m * 0.3} y2={W} />
            <text transform={`translate(${-m * 0.6} ${W / 2}) rotate(-90)`} textAnchor="middle" stroke="none">{W} mm</text>
          </g>
          <rect x={0} y={0} width={L} height={W} rx={fs * 0.6} fill={`url(#w${uid})`} stroke="var(--line)" strokeWidth={fs * 0.15} />
          <rect x={0} y={0} width={L} height={W} rx={fs * 0.6} fill={`url(#h${uid})`} />
          <rect x={trim} y={trim} width={L - 2 * trim} height={W - 2 * trim} fill="none" stroke="var(--muted)" strokeOpacity="0.5" strokeDasharray={`${fs} ${fs * 0.7}`} strokeWidth={fs * 0.12} />
          {s.placements.map((p, i) => { const c = colorOf(p); const lf = Math.min(fs * 2.3, Math.max(fs * 1.15, Math.min(p.w, p.h) / 5.5)); const fits = p.w > lf * 6 && p.h > lf * 2.4; const x = trim + p.x, y = trim + p.y; return (
            <g key={i} filter={`url(#s${uid})`}>
              <rect x={x} y={y} width={p.w} height={p.h} rx={fs * 0.25} fill={c} fillOpacity={0.88} stroke="#fff" strokeOpacity="0.55" strokeWidth={fs * 0.12}><title>{`${p.name}: ${p.w} x ${p.h} mm${p.rotated ? ' (rotated)' : ''}`}</title></rect>
              {fits && <text x={x + p.w / 2} y={y + p.h / 2} textAnchor="middle" fill="#fff" fontSize={lf} fontWeight={600} fontFamily="Geist Variable, sans-serif" style={{ paintOrder: 'stroke' }} stroke="rgba(0,0,0,0.25)" strokeWidth={lf * 0.1}>
                <tspan x={x + p.w / 2} dy="-0.15em">{p.name}</tspan><tspan x={x + p.w / 2} dy="1.25em" fontWeight={400} fillOpacity={0.9}>{p.w} x {p.h}{p.rotated ? ' ↻' : ''}</tspan></text>}
              {!fits && p.w > fs * 2 && p.h > fs * 2 && <text x={x + p.w / 2} y={y + p.h / 2 + fs * 0.35} textAnchor="middle" fill="#fff" fontSize={fs * 0.8} fontWeight={600}>{i + 1}</text>}
            </g>) })}
        </svg>
      </div>
    </figure>
  )
}

function Detail({ id }: { id: string }) {
  const nav = useNavigate(); const qc = useQueryClient()
  const q = useQuery({ queryKey: ['cutting-list', id], queryFn: async () => (await api.get<CuttingList>(`/cutting-lists/${id}/`)).data })
  const run = useQuery({ queryKey: ['cutting-run', id, q.data?.latest_run?.id], enabled: !!q.data?.latest_run, placeholderData: keepPreviousData, queryFn: async () => (await api.get<OptRun[]>(`/cutting-lists/${id}/runs/`)).data[0] })
  const [name, setName] = useState(''); const [parts, setParts] = useState<CuttingPart[]>([]); const [sheet, setSheet] = useState({ sheet_length: 2800, sheet_width: 2070, kerf: 3, trim: 10 }); const [rot, setRot] = useState(true); const [del, setDel] = useState(false); const [dirty, setDirty] = useState(false)
  useEffect(() => { const l = q.data; if (l) { setName(l.name); setParts(l.parts); setSheet({ sheet_length: l.sheet_length, sheet_width: l.sheet_width, kerf: Number(l.kerf), trim: Number(l.trim) }); setDirty(false) } }, [q.data])
  const inval = () => { qc.invalidateQueries({ queryKey: ['cutting-list', id] }); qc.invalidateQueries({ queryKey: ['cutting-lists'] }) }
  const save = useMutation({ mutationFn: () => api.patch(`/cutting-lists/${id}/`, { name: name.trim(), ...sheet, parts: parts.map(({ id: _i, ...p }) => ({ ...p, width: Number(p.width), height: Number(p.height), thickness: Number(p.thickness) })) }),
    onSuccess: () => { toast.success('Cutting list saved'); inval() }, onError: (e) => toast.error(apiError(e).message) })
  const optimize = useMutation({ mutationFn: async () => { if (dirty) await save.mutateAsync(); return (await api.post<OptRun>(`/cutting-lists/${id}/optimize/`, { allow_rotation: rot })).data },
    onSuccess: () => { toast.success('Optimization complete'); inval(); qc.invalidateQueries({ queryKey: ['cutting-run', id] }) }, onError: (e) => toast.error(apiError(e).message) })
  const remove = useMutation({ mutationFn: () => api.delete(`/cutting-lists/${id}/`), onSuccess: () => { qc.invalidateQueries({ queryKey: ['cutting-lists'] }); toast.success('Deleted'); nav('/app/cutting-lists') } })
  const exp = async (k: 'pdf' | 'xlsx') => { try { if (dirty) await save.mutateAsync(); await downloadBlob(`/cutting-lists/${id}/export/${k}/`, `${name || 'cutting-list'}.${k}`) } catch (e) { toast.error(apiError(e).message) } }
  const edit = (i: number, patch: Partial<CuttingPart>) => { setParts(parts.map((p, j) => (j === i ? { ...p, ...patch } : p))); setDirty(true) }

  if (q.isLoading) return <div className="p-8"><Skeleton className="h-96" /></div>
  if (q.isError || !q.data) return <div className="p-8"><ErrorState message="Cutting list not found." /></div>
  const r = run.data?.result
  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 sm:p-8">
      <Breadcrumbs items={[{ label: 'Cutting lists', to: '/app/cutting-lists' }, { label: q.data.name }]} />
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-56 flex-1"><Input label="List name" value={name} onChange={(e) => { setName(e.target.value); setDirty(true) }} maxLength={160} /></div>
        <Button variant="secondary" icon={<Save size={16} />} loading={save.isPending} disabled={!dirty} onClick={() => save.mutate()}>Save</Button>
        <Button variant="secondary" icon={<FileText size={16} />} onClick={() => exp('pdf')}>PDF</Button>
        <Button variant="secondary" icon={<FileSpreadsheet size={16} />} onClick={() => exp('xlsx')}>Excel</Button>
        <Button variant="danger" icon={<Trash2 size={16} />} aria-label="Delete list" onClick={() => setDel(true)} />
      </div>
      <Card className="overflow-x-auto">
        <table className="w-full min-w-[46rem] text-sm"><thead><tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">{['Part', 'Width', 'Height', 'Thick.', 'Qty', 'Material', 'Rotate', ''].map((h) => <th key={h} className="px-3 py-2.5 font-medium">{h}</th>)}</tr></thead>
          <tbody>{parts.map((p, i) => (
            <tr key={i} className="border-b border-line/60 last:border-0">
              <td className="px-3 py-1.5"><input aria-label="Part name" value={p.name} onChange={(e) => edit(i, { name: e.target.value })} className="h-9 w-full rounded-md border border-transparent bg-transparent px-2 hover:border-line focus:border-primary" /></td>
              {(['width', 'height', 'thickness', 'quantity'] as const).map((k) => <td key={k} className="px-3 py-1.5"><input aria-label={k} type="number" value={String(p[k])} onChange={(e) => edit(i, { [k]: e.target.value === '' ? '' : Number(e.target.value) } as Partial<CuttingPart>)} className="num h-9 w-20 rounded-md border border-transparent bg-transparent px-2 hover:border-line focus:border-primary" /></td>)}
              <td className="px-3 py-1.5"><input aria-label="Material" value={p.material} onChange={(e) => edit(i, { material: e.target.value.toUpperCase() })} className="h-9 w-24 rounded-md border border-transparent bg-transparent px-2 hover:border-line focus:border-primary" /></td>
              <td className="px-3 py-1.5"><input type="checkbox" aria-label="Allow rotation" checked={p.can_rotate} onChange={(e) => edit(i, { can_rotate: e.target.checked })} /></td>
              <td className="px-3 py-1.5 text-right"><button aria-label="Remove part" onClick={() => { setParts(parts.filter((_, j) => j !== i)); setDirty(true) }} className="rounded-md p-1.5 text-muted hover:bg-danger/10 hover:text-danger"><Trash2 size={15} /></button></td></tr>))}</tbody></table>
        <div className="border-t border-line p-3"><Button size="sm" variant="ghost" icon={<Plus size={14} />} onClick={() => { setParts([...parts, { name: 'New part', width: 300, height: 600, thickness: 18, quantity: 1, material: 'MDF', can_rotate: false, edge_w: 0, edge_h: 0, edge_note: '' }]); setDirty(true) }}>Add part</Button></div>
      </Card>
      <Card className="p-4"><h2 className="mb-3 text-sm font-semibold">Sheet settings</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <NumberField label="Length" unit="mm" value={sheet.sheet_length} onChange={(n) => { setSheet({ ...sheet, sheet_length: n }); setDirty(true) }} />
          <NumberField label="Width" unit="mm" value={sheet.sheet_width} onChange={(n) => { setSheet({ ...sheet, sheet_width: n }); setDirty(true) }} />
          <NumberField label="Saw kerf" unit="mm" step={0.5} value={sheet.kerf} onChange={(n) => { setSheet({ ...sheet, kerf: n }); setDirty(true) }} />
          <NumberField label="Edge trim" unit="mm" value={sheet.trim} onChange={(n) => { setSheet({ ...sheet, trim: n }); setDirty(true) }} />
          <label className="flex items-end gap-2 pb-2 text-sm"><input type="checkbox" checked={rot} onChange={(e) => setRot(e.target.checked)} />Allow rotation</label></div>
        <p className="mt-2 text-xs text-muted">HDF parts use their own catalogue sheet size. Other materials use these settings unless a catalogue material matches.</p>
        <Button className="mt-4" icon={<Layers size={16} />} loading={optimize.isPending} disabled={!parts.length} onClick={() => optimize.mutate()}>Optimize layout</Button></Card>
      {r && (<section className="space-y-4" aria-live="polite">
        <h2 className="text-lg font-semibold">Optimization result</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4"><Stat label="Sheets" value={r.summary.sheet_count} /><Stat label="Utilization" value={`${r.summary.utilization_pct}%`} /><Stat label="Waste" value={`${r.summary.waste_pct}%`} /><Stat label="Est. cost" value={r.summary.estimated_cost != null ? `$${r.summary.estimated_cost}` : 'n/a'} hint={r.summary.estimated_cost == null ? 'No sheet price set' : undefined} /></div>
        {r.unplaced.length > 0 && <p role="alert" className="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger">Parts larger than the sheet were not placed: {r.unplaced.map((u) => `${u.name} (${u.width} x ${u.height})`).join(', ')}.</p>}
        {r.groups.map((g) => (
          <div key={g.key} className="space-y-3 rounded-2xl border border-line bg-sidebar/40 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="flex items-center gap-2 text-base font-semibold"><Layers size={17} className="text-primary" />{g.key}</h3>
              <span className="num text-xs text-muted">{g.result.summary.sheet_count} x {g.result.sheet.length} x {g.result.sheet.width} mm · {g.result.summary.utilization_pct}% used · {g.result.summary.waste_pct}% waste{g.result.summary.last_sheet_offcut ? ` · leftover strip ${g.result.summary.last_sheet_offcut.width} mm (${g.result.summary.last_sheet_offcut.area_m2} m2)` : ''}{g.estimated_cost != null ? ` · $${g.estimated_cost}` : ''}</span></div>
            {g.result.legend && <ul className="flex flex-wrap gap-2" aria-label="Legend">{g.result.legend.map((l) => <li key={l.name} className="flex items-center gap-2 rounded-full border border-line bg-card px-2.5 py-1 text-xs"><span className="h-3 w-3 rounded" style={{ background: l.color }} />{l.name}<span className="num text-muted">{l.quantity} x {l.width} x {l.height}</span></li>)}</ul>}
            <div className="grid gap-4 lg:grid-cols-2">{g.result.sheets.map((_, i) => <SheetSvg key={i} group={g} idx={i} />)}</div></div>))}
        <p className="text-xs text-muted">{run.data?.result.disclaimer}</p></section>)}
      <ConfirmDialog open={del} onClose={() => setDel(false)} title="Delete cutting list" message="This permanently deletes the list and its optimization history." loading={remove.isPending} onConfirm={() => remove.mutate()} />
      <RightPanel><PanelSection title="Totals"><dl className="space-y-2 text-sm">{[['Pieces', q.data.totals.pieces], ['Area', `${q.data.totals.area_m2} m2`], ['Edge banding', `${q.data.totals.edge_banding_m} m`]].map(([k, v]) => <div key={k} className="flex justify-between"><dt className="text-muted">{k}</dt><dd className="num">{v}</dd></div>)}</dl></PanelSection>
        {r && <PanelSection title="Sheet usage"><Progress value={r.summary.utilization_pct} tone="success" label="Utilization" /><p className="num mt-2 text-xs text-muted">{r.summary.utilization_pct}% of purchased sheet area is used by parts.</p></PanelSection>}
        <PanelSection title="Notice"><p className="text-xs text-muted">Cutting layouts are guillotine layouts for professional review. Verify grain direction, defects and machine limits before cutting.</p></PanelSection></RightPanel>
    </div>
  )
}

function ListView() {
  const nav = useNavigate(); const qc = useQueryClient()
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ['cutting-lists'], queryFn: async () => (await api.get<Page<CuttingList>>('/cutting-lists/')).data })
  const blank = useMutation({ mutationFn: async () => (await api.post<CuttingList>('/cutting-lists/', { name: 'Untitled cutting list', parts: [] })).data, onSuccess: (l) => { qc.invalidateQueries({ queryKey: ['cutting-lists'] }); nav(`/app/cutting-lists/${l.id}`) }, onError: (e) => toast.error(apiError(e).message) })
  return (
    <div className="mx-auto max-w-5xl p-4 sm:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="text-2xl font-bold">Cutting lists</h1>
        <div className="flex gap-2"><Link to="/app/calculator"><Button variant="secondary" icon={<Calculator size={16} />}>From calculator</Button></Link><Button icon={<Plus size={16} />} loading={blank.isPending} onClick={() => blank.mutate()}>Blank list</Button></div></div>
      <div className="mt-6">{isLoading ? <div className="grid gap-3 sm:grid-cols-2">{[0, 1].map((i) => <Skeleton key={i} className="h-28" />)}</div> : isError ? <ErrorState message="Could not load cutting lists." onRetry={refetch} />
        : data?.results.length ? <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{data.results.map((l) => <HoverCard key={l.id} as="button" onClick={() => nav(`/app/cutting-lists/${l.id}`)} className="p-4"><p className="font-medium">{l.name}</p>
          <p className="num mt-1 text-xs text-muted">{l.totals.pieces} pieces · {l.totals.area_m2} m2</p><p className="mt-1 text-xs text-muted">{l.latest_run ? `${l.latest_run.sheet_count} sheets · ${l.latest_run.utilization_pct}% used` : 'Not optimized yet'} · {fmtAgo(l.updated_at)}</p></HoverCard>)}</div>
          : <EmptyState icon={<Scissors size={22} />} title="No cutting lists yet" text="Generate one from a cabinet calculation or start with a blank list." action={<Link to="/app/calculator"><Button>Open calculator</Button></Link>} />}</div>
    </div>
  )
}

export default function CuttingLists() { const { id } = useParams(); return id ? <Detail id={id} /> : <ListView /> }
