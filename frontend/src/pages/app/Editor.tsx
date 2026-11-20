import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Box as BoxIcon, Download, FileSpreadsheet, FileText, Grid2x2, Save } from 'lucide-react'
import { api, apiError, downloadBlob } from '../../lib/api'
import type { Box, CabinetInput, CuttingList, Design, Material } from '../../lib/types'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input, Select } from '../../components/ui/Field'
import { Tabs } from '../../components/ui/Tabs'
import { Skeleton } from '../../components/ui/Misc'
import { toast } from '../../components/ui/Toast'
import { CabinetViewer } from '../../components/three/LazyViewer'
import { CabinetForm, DEFAULT_INPUT, FrontView, Swatches } from '../../components/CabinetPanel'
import { useCalculation, useGeometry, useMaterials, useMeta, useProjects, useTemplates } from '../../hooks/queries'
import { useL } from '../../lib/i18n'
import { PanelSection, RightPanel } from '../../layouts/RightPanel'


export default function Editor() {
  const L = useL(); const meta = useMeta(); const CATS: [string, string][] = [['', 'All'], ...(meta.data?.furniture_categories.map((c): [string, string] => [c.slug, L(c.label)]) ?? [])]
  const [params] = useSearchParams(); const qc = useQueryClient()
  const [cat, setCat] = useState(params.get('category') ?? ''); const [input, setInput] = useState<CabinetInput>(DEFAULT_INPUT); const [color, setColor] = useState('#c9a27a')
  const [view, setView] = useState<'3d' | '2d'>('3d'); const [wire, setWire] = useState(false); const [dims, setDims] = useState(true); const [sel, setSel] = useState<Box | null>(null)
  const [name, setName] = useState('Untitled design'); const [designId, setDesignId] = useState<number | null>(null); const [projectId, setProjectId] = useState(params.get('project') ?? ''); const [matId, setMatId] = useState('')
  const templates = useTemplates(cat || undefined); const materials = useMaterials(); const projects = useProjects({ page_size: 100 })
  const valid = Object.values(input).every(Number.isFinite)
  const geo = useGeometry(input, color, valid); const calc = useCalculation(input, valid)
  const errs = geo.isError ? apiError(geo.error).fields : {}

  const wantedTemplate = params.get('template'); const designParam = params.get('design')
  const all = useTemplates()
  useEffect(() => { if (wantedTemplate && all.data) { const t = all.data.find((x) => x.slug === wantedTemplate); if (t) { setInput(t.defaults); setName(t.name) } } }, [wantedTemplate, all.data])
  const cab = params.get('cab')
  useEffect(() => { if (cab) { const n = cab.split(',').map(Number); if (n.length === 7 && n.every(Number.isFinite)) setInput({ width: n[0], height: n[1], depth: n[2], thickness: n[3], shelves: n[4], doors: n[5], drawers: n[6] }) } }, [cab])
  const design = useQuery({ queryKey: ['design', designParam], enabled: !!designParam, queryFn: async () => (await api.get<Design>(`/designs/${designParam}/`)).data })
  useEffect(() => { const d = design.data; if (d) { const c = d.config as { input?: CabinetInput; color?: string }; if (c.input) setInput(c.input); if (c.color) setColor(c.color); setName(d.name); setDesignId(d.id); if (d.project) setProjectId(String(d.project)) } }, [design.data])

  const pickMaterial = (id: string) => { setMatId(id); const m = materials.data?.find((x) => String(x.id) === id); if (m) { setColor(m.color); setInput((i) => ({ ...i, thickness: Number(m.thickness) })) } }
  const save = useMutation({
    mutationFn: async () => { const body = { name: name.trim() || 'Untitled design', kind: 'furniture', project: projectId ? Number(projectId) : null, config: { input, color, material: matId || null } }
      return designId ? (await api.patch<Design>(`/designs/${designId}/`, body)).data : (await api.post<Design>('/designs/', body)).data },
    onSuccess: (d) => { setDesignId(d.id); toast.success('Design saved'); qc.invalidateQueries({ queryKey: ['designs'] }); qc.invalidateQueries({ queryKey: ['summary'] }) }, onError: (e) => toast.error(apiError(e).message) })
  const exp3d = async (fmt: string) => { try { await downloadBlob(`/geometry/export/${fmt}/`, `${name || 'design'}.${fmt}`, 'post', { ...input, color }) } catch (e) { toast.error(apiError(e).message) } }
  const expCut = useMutation({
    mutationFn: async (kind: 'pdf' | 'xlsx') => { const l = (await api.post<CuttingList>('/cutting-lists/from-calculation/', { ...input, name, ...(projectId ? { project: Number(projectId) } : {}) })).data
      await api.post(`/cutting-lists/${l.id}/optimize/`, {}); await downloadBlob(`/cutting-lists/${l.id}/export/${kind}/`, `${name}.${kind}`) },
    onSuccess: () => toast.success('Export ready'), onError: (e) => toast.error(apiError(e).message) })
  const matOpts = useMemo(() => [{ value: '', label: 'Default' }, ...(materials.data?.filter((m: Material) => ['MDF', 'LDSP', 'PLYWOOD'].includes(m.kind)).map((m) => ({ value: m.id, label: m.name })) ?? [])], [materials.data])
  const s = calc.data?.summary
  return (
    <div className="flex min-h-full flex-col">
      <div className="grid flex-1 gap-0 lg:grid-cols-[16rem_1fr]">
        <aside className="border-b border-line p-4 lg:border-b-0 lg:border-r" aria-label="Furniture library">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Categories</h2>
          <div className="flex flex-wrap gap-1.5">{CATS.map(([v, l]) => <button key={v} onClick={() => setCat(v)} aria-pressed={cat === v} className={`rounded-full border px-2.5 py-1 text-xs ${cat === v ? 'border-primary bg-primary/15 text-fg' : 'border-line text-muted hover:text-fg'}`}>{l}</button>)}</div>
          <h2 className="mb-2 mt-5 text-xs font-semibold uppercase tracking-wide text-muted">Components</h2>
          <ul className="space-y-1.5">{templates.isLoading ? [0, 1, 2].map((i) => <Skeleton key={i} className="h-12" />) : templates.data?.map((t) => (
            <li key={t.id}><button onClick={() => { setInput(t.defaults); setName(t.name); setDesignId(null) }} className="w-full rounded-lg border border-line bg-card px-3 py-2 text-left text-sm transition-colors hover:border-primary/50 hover:bg-card2">
              <span className="block font-medium">{t.name}</span><span className="num text-xs text-muted">{t.defaults.width} x {t.defaults.height} x {t.defaults.depth}</span></button></li>))}</ul>
        </aside>
        <div className="min-w-0 p-4 sm:p-6">
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <div className="min-w-48 flex-1"><Input label="Design name" value={name} onChange={(e) => setName(e.target.value)} maxLength={160} /></div>
            <Tabs tabs={[{ id: '3d', label: '3D', icon: <BoxIcon size={15} /> }, { id: '2d', label: '2D front', icon: <Grid2x2 size={15} /> }]} value={view} onChange={setView} />
            <Button icon={<Save size={16} />} loading={save.isPending} disabled={!valid} onClick={() => save.mutate()}>{designId ? 'Update' : 'Save design'}</Button>
          </div>
          {Object.keys(errs).length > 0 && <p role="alert" className="mb-3 rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger">{Object.values(errs)[0]}</p>}
          {geo.data ? (view === '3d' ? <CabinetViewer boxes={geo.data.boxes} dims={geo.data.dimensions} showDims={dims} wire={wire} className="h-[min(52vh,500px)]" />
            : <Card className="flex h-[min(52vh,500px)] items-center justify-center p-4"><FrontView boxes={geo.data.boxes} dims={geo.data.dimensions} selected={sel?.name} onSelect={setSel} /></Card>) : <Skeleton className="h-[min(52vh,500px)]" />}
          <div className="mt-3 flex flex-wrap gap-4 text-sm text-muted">
            <label className="flex items-center gap-2"><input type="checkbox" checked={dims} onChange={(e) => setDims(e.target.checked)} />Dimensions</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={wire} onChange={(e) => setWire(e.target.checked)} />Wireframe</label>
          </div>
        </div>
      </div>
      <footer className="flex flex-wrap items-center gap-x-6 gap-y-3 border-t border-line bg-sidebar px-4 py-3 text-sm sm:px-6">
        <div className="flex gap-5"><span><span className="text-muted">Panels </span><span className="num font-medium">{s?.panel_count ?? '-'}</span></span><span><span className="text-muted">Area </span><span className="num font-medium">{s ? `${s.total_area_m2} m2` : '-'}</span></span><span><span className="text-muted">Edge </span><span className="num font-medium">{s ? `${s.edge_banding_m} m` : '-'}</span></span></div>
        <div className="ml-auto flex flex-wrap items-center gap-2"><Download size={15} className="text-muted" />
          {['glb', 'gltf', 'obj'].map((f) => <Button key={f} size="sm" variant="secondary" disabled={!valid || !!Object.keys(errs).length} onClick={() => exp3d(f)}>{f.toUpperCase()}</Button>)}
          <Button size="sm" variant="secondary" icon={<FileText size={14} />} loading={expCut.isPending && expCut.variables === 'pdf'} disabled={!calc.data} onClick={() => expCut.mutate('pdf')}>Cutting PDF</Button>
          <Button size="sm" variant="secondary" icon={<FileSpreadsheet size={14} />} loading={expCut.isPending && expCut.variables === 'xlsx'} disabled={!calc.data} onClick={() => expCut.mutate('xlsx')}>Excel</Button></div>
      </footer>
      <RightPanel>
        <PanelSection title="Dimensions"><CabinetForm value={input} onChange={(v) => { setInput(v); setSel(null) }} errors={errs} /></PanelSection>
        <PanelSection title="Material and color"><div className="space-y-3"><Select label="Board" value={matId} onChange={(e) => pickMaterial(e.target.value)} options={matOpts} /><Swatches value={color} onChange={setColor} /></div></PanelSection>
        <PanelSection title="Project"><Select label="Attach to project" value={projectId} onChange={(e) => setProjectId(e.target.value)} options={[{ value: '', label: 'None' }, ...(projects.data?.results.map((p) => ({ value: p.id, label: p.name })) ?? [])]} /></PanelSection>
        <PanelSection title="Component properties">{sel ? <dl className="space-y-1.5 text-sm">{[['Name', sel.name], ['Type', sel.kind], ['Width', `${sel.sx} mm`], ['Height', `${sel.sy} mm`], ['Depth', `${sel.sz} mm`], ['Position', `${sel.x}, ${sel.y}, ${sel.z}`]].map(([k, v]) => <div key={k} className="flex justify-between"><dt className="text-muted">{k}</dt><dd className="num capitalize">{v}</dd></div>)}</dl>
          : <p className="text-xs text-muted">Select a component in the 2D front view to inspect it.</p>}</PanelSection>
        {!!geo.data?.warnings.length && <PanelSection title="Warnings"><ul className="space-y-1.5 text-xs text-warning">{geo.data.warnings.map((w) => <li key={w}>{w}</li>)}</ul></PanelSection>}
      </RightPanel>
    </div>
  )
}
