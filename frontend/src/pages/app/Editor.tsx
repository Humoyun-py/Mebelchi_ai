import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, Download, FileSpreadsheet, FileText, Save } from 'lucide-react'
import { api, apiError, downloadBlob } from '../../lib/api'
import type { Box, CabinetInput, CuttingList, Design, Template } from '../../lib/types'
import { BASE_INPUT, type EditorDoc, geometryBody, fromConfig, isValidInput, newDoc, snapshot, toConfig } from '../../lib/editor'
import { DEFAULT_TYPE, TYPE_PRESETS, type TypeState } from '../../lib/cabinet'
import type { View } from '../../lib/editor3d'
import { Button } from '../../components/ui/Button'
import { Badge, ErrorState, Skeleton } from '../../components/ui/Misc'
import { Input, NumberField, Select, Switch } from '../../components/ui/Field'
import { ConfirmDialog } from '../../components/ui/Modal'
import { toast } from '../../components/ui/Toast'
import { CabinetViewer } from '../../components/three/LazyViewer'
import { CabinetForm, TypeForm } from '../../components/CabinetPanel'
import { ColorsPanel, ComponentList, ComponentProperties, ConsistencyBadge, ViewBar } from '../../components/editor/EditorPanels'
import { useCalculation, useGeometry, useMaterials, useMeta, useProjects, useTemplates } from '../../hooks/queries'
import { useL, useT } from '../../lib/i18n'

const HANDLES = ['bar', 'knob', 'none'] as const
const BACKS = ['HDF', 'PLYWOOD', 'MDF']
const Section = ({ title, children }: { title: string; children: React.ReactNode }) => <section className="border-b border-line px-4 py-4 last:border-0"><h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted">{title}</h3>{children}</section>

interface Initial { doc: EditorDoc; designId: number | null }

/** Route component: works out what to open (a saved design, a template, sizes from the calculator or nothing) and mounts the editor with it. */
export default function Editor() {
  const t = useT(); const [params] = useSearchParams()
  const [designParam] = useState(() => params.get('design')); const [templateParam] = useState(() => params.get('template')); const [cabParam] = useState(() => params.get('cab'))
  const [projectParam] = useState(() => params.get('project') ?? '')
  const design = useQuery({ queryKey: ['design', designParam], enabled: !!designParam, retry: false, queryFn: async () => (await api.get<Design>(`/designs/${designParam}/`)).data })
  const templates = useTemplates(); const wantsTemplate = !!templateParam && !designParam
  if (designParam && design.isError) return <div className="mx-auto max-w-xl p-6"><ErrorState message={t('ed.loadErr')} /><Link to="/app/editor" className="mt-3 inline-block text-sm text-primary hover:underline">{t('ed.newDesign')}</Link></div>
  if ((designParam && !design.data) || (wantsTemplate && !templates.data)) return <div className="space-y-3 p-6"><Skeleton className="h-10 w-64" /><Skeleton className="h-[420px]" /></div>
  let initial: Initial = { doc: newDoc({ projectId: projectParam }), designId: null }
  if (design.data) initial = { doc: fromConfig(design.data.config as never, design.data.name, design.data.project), designId: design.data.id }
  else if (wantsTemplate) { const tpl = templates.data?.find((x) => x.slug === templateParam); if (tpl) initial = { doc: templateDoc(tpl, projectParam), designId: null } }
  else if (cabParam) { const n = cabParam.split(',').map(Number); if (n.length === 7 && n.every(Number.isFinite)) initial = { doc: newDoc({ projectId: projectParam, input: { ...BASE_INPUT, width: n[0], height: n[1], depth: n[2], thickness: n[3], shelves: n[4], doors: n[5], drawers: n[6] } }), designId: null } }
  return <EditorBody initial={initial} />
}

const templateDoc = (tpl: Template, projectId: string): EditorDoc => newDoc({ name: tpl.name, projectId, input: { ...BASE_INPUT, ...tpl.defaults } })

function EditorBody({ initial }: { initial: Initial }) {
  const t = useT(); const L = useL(); const meta = useMeta(); const nav = useNavigate(); const qc = useQueryClient()
  const [doc, setDoc] = useState<EditorDoc>(initial.doc); const [designId, setDesignId] = useState<number | null>(initial.designId)
  const [saved, setSaved] = useState(() => snapshot(initial.doc))
  const [view, setView] = useState<View>('perspective'); const [resetKey, setResetKey] = useState(0); const [dims, setDims] = useState(true); const [wire, setWire] = useState(false); const [selName, setSelName] = useState<string | null>(null)
  const [cat, setCat] = useState(''); const [replace, setReplace] = useState<Template | null>(null)
  const templates = useTemplates(cat || undefined); const materials = useMaterials(); const projects = useProjects({ page_size: 100 })
  const dirty = snapshot(doc) !== saved
  const valid = isValidInput(doc.input)
  const geo = useGeometry(geometryBody(doc), undefined, valid); const calc = useCalculation(doc.input, valid)
  const errs = geo.isError ? apiError(geo.error).fields : {}
  const sel: Box | null = geo.data?.boxes.find((b) => b.name === selName) ?? null
  const set = (patch: Partial<EditorDoc>) => setDoc((d) => ({ ...d, ...patch }))
  const setInput = (patch: Partial<CabinetInput>) => setDoc((d) => ({ ...d, input: { ...d.input, ...patch } }))

  useEffect(() => { if (!dirty) return; const h = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = '' }; window.addEventListener('beforeunload', h); return () => window.removeEventListener('beforeunload', h) }, [dirty])

  const typeState: TypeState = { cabinet_type: doc.input.cabinet_type ?? 'standard', edge_thickness: doc.input.edge_thickness ?? 0, plinth_height: doc.input.plinth_height ?? DEFAULT_TYPE.plinth_height,
    sliding_overlap: doc.input.sliding_overlap ?? DEFAULT_TYPE.sliding_overlap, track_top: doc.input.track_top ?? DEFAULT_TYPE.track_top, track_bottom: doc.input.track_bottom ?? DEFAULT_TYPE.track_bottom, rail_width: doc.input.rail_width ?? DEFAULT_TYPE.rail_width }
  const changeType = (n: TypeState) => { const preset = n.cabinet_type !== typeState.cabinet_type ? TYPE_PRESETS[n.cabinet_type] : undefined; setInput({ ...(preset ?? {}), ...n }) }
  const pickMaterial = (id: string) => {
    const m = materials.data?.find((x) => String(x.id) === id)
    if (!m) { set({ materialId: '' }); return }
    setDoc((d) => ({ ...d, materialId: id, input: { ...d.input, material: m.kind, thickness: Number(m.thickness) }, colors: { ...d.colors, carcass: m.color, fronts: m.color } }))
  }
  const openTemplate = (tpl: Template) => { if (dirty) setReplace(tpl); else applyTemplate(tpl) }
  const applyTemplate = (tpl: Template) => { const d = templateDoc(tpl, doc.projectId); setDoc(d); setDesignId(null); setSaved(snapshot(d)); setSelName(null); setReplace(null) }

  const body = () => ({ name: doc.name.trim() || t('ed.newDesign'), kind: 'furniture', project: doc.projectId ? Number(doc.projectId) : null, config: toConfig(doc) })
  const done = (d: Design, snap: string) => { setDesignId(d.id); setSaved(snap); toast.success(t('ed.saved')); qc.invalidateQueries({ queryKey: ['designs'] }); qc.invalidateQueries({ queryKey: ['summary'] }); qc.invalidateQueries({ queryKey: ['design', String(d.id)] }) }
  const save = useMutation({
    mutationFn: async (asNew: boolean) => { const snap = snapshot(doc); const b = asNew ? { ...body(), name: `${(doc.name.trim() || t('ed.newDesign')).slice(0, 150)} (${t('ed.copy')})` } : body()
      const d = designId && !asNew ? (await api.patch<Design>(`/designs/${designId}/`, b)).data : (await api.post<Design>('/designs/', b)).data; return { d, snap, asNew } },
    onSuccess: ({ d, snap, asNew }) => { if (asNew) set({ name: d.name }); done(d, asNew ? snapshot({ ...doc, name: d.name }) : snap); nav(`/app/editor?design=${d.id}`, { replace: true }) },
    onError: (e) => toast.error(apiError(e).message) })
  const exp3d = async (fmt: string) => { try { await downloadBlob(`/geometry/export/${fmt}/`, `${doc.name || 'design'}.${fmt}`, 'post', geometryBody(doc)) } catch (e) { toast.error(apiError(e).message) } }
  const expCut = useMutation({
    mutationFn: async (kind: 'pdf' | 'xlsx') => { const l = (await api.post<CuttingList>('/cutting-lists/from-calculation/', { ...doc.input, name: doc.name, ...(doc.projectId ? { project: Number(doc.projectId) } : {}) })).data
      await api.post(`/cutting-lists/${l.id}/optimize/`, {}); await downloadBlob(`/cutting-lists/${l.id}/export/${kind}/`, `${doc.name}.${kind}`) },
    onSuccess: () => toast.success(t('ed.exportReady')), onError: (e) => toast.error(apiError(e).message) })

  const cats: [string, string][] = [['', t('common.all')], ...(meta.data?.furniture_categories.map((c): [string, string] => [c.slug, L(c.label)]) ?? [])]
  const matOpts = useMemo(() => [{ value: '', label: t('ed.boardDefault') }, ...(materials.data?.filter((m) => ['MDF', 'LDSP', 'PLYWOOD'].includes(m.kind)).map((m) => ({ value: m.id, label: m.name })) ?? [])], [materials.data, t])
  const s = calc.data?.summary; const blocked = !valid || Object.keys(errs).length > 0
  const alertText = Object.values(errs)[0] ?? (geo.isError ? apiError(geo.error).message : '')

  return (
    <div className="flex min-h-full flex-col">
      <div className="grid flex-1 xl:grid-cols-[15rem_minmax(0,1fr)_21rem]">
        <aside className="order-3 border-t border-line p-4 xl:order-1 xl:border-r xl:border-t-0" aria-label={t('ed.library')}>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{t('ed.categories')}</h2>
          <div className="flex flex-wrap gap-1.5">{cats.map(([v, l]) => <button key={v} onClick={() => setCat(v)} aria-pressed={cat === v} className={`rounded-full border px-2.5 py-1 text-xs ${cat === v ? 'border-primary bg-primary/15 text-fg' : 'border-line text-muted hover:text-fg'}`}>{l}</button>)}</div>
          <h2 className="mb-2 mt-5 text-xs font-semibold uppercase tracking-wide text-muted">{t('ed.templates')}</h2>
          <ul className="space-y-1.5">{templates.isLoading ? [0, 1, 2].map((i) => <Skeleton key={i} className="h-12" />) : templates.data?.map((tpl) => (
            <li key={tpl.id}><button onClick={() => openTemplate(tpl)} className="w-full rounded-lg border border-line bg-card px-3 py-2 text-left text-sm transition-colors hover:border-primary/50 hover:bg-card2">
              <span className="block font-medium">{tpl.name}</span><span className="num text-xs text-muted">{tpl.defaults.width} x {tpl.defaults.height} x {tpl.defaults.depth}</span></button></li>))}</ul>
        </aside>

        <section className="order-1 min-w-0 p-4 sm:p-6 xl:order-2" aria-label={t('ed.stage')}>
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <div className="min-w-48 flex-1"><Input label={t('ed.name')} value={doc.name} onChange={(e) => set({ name: e.target.value })} maxLength={160} /></div>
            {dirty ? <Badge tone="warning">{t('ed.unsaved')}</Badge> : designId ? <Badge tone="success">{t('ed.savedBadge')}</Badge> : null}
            <Button icon={<Save size={16} />} loading={save.isPending && !save.variables} disabled={blocked} onClick={() => save.mutate(false)}>{designId ? t('ed.update') : t('ed.save')}</Button>
            {designId && <Button variant="secondary" icon={<Copy size={16} />} loading={save.isPending && !!save.variables} disabled={blocked} onClick={() => save.mutate(true)}>{t('ed.saveNew')}</Button>}
          </div>
          {alertText && <p role="alert" className="mb-3 rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger">{alertText}</p>}
          {geo.data ? <CabinetViewer boxes={geo.data.boxes} dims={geo.data.dimensions} showDims={dims} wire={wire} view={view} resetKey={resetKey} selected={selName} onSelect={(b) => setSelName(b?.name ?? null)} className="h-[min(58vh,560px)]" />
            : <Skeleton className="h-[min(58vh,560px)]" />}
          <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2">
            <ViewBar view={view} onView={(v) => { setView(v); setResetKey((k) => k + 1) }} onReset={() => { setView('perspective'); setResetKey((k) => k + 1) }} />
            <label className="flex items-center gap-2 text-sm text-muted"><Switch checked={dims} onChange={setDims} label={t('ed.dims')} />{t('ed.dims')}</label>
            <label className="flex items-center gap-2 text-sm text-muted"><Switch checked={wire} onChange={setWire} label={t('ed.wire')} />{t('ed.wire')}</label>
          </div>
          <div className="mt-3"><ConsistencyBadge c={geo.data?.consistency} /></div>
        </section>

        <aside className="order-2 border-t border-line xl:order-3 xl:border-l xl:border-t-0" aria-label={t('ed.controls')}>
          <Section title={t('ed.sec.type')}><div className="space-y-3"><TypeForm value={typeState} onChange={changeType} errors={errs} /><CabinetForm value={doc.input} onChange={(v) => { setInput(v); }} errors={errs} /></div></Section>
          <Section title={t('ed.sec.handles')}><Select label={t('ed.handle.label')} value={doc.input.handle_style ?? 'bar'} onChange={(e) => setInput({ handle_style: e.target.value as 'bar' | 'knob' | 'none' })} error={errs.handle_style}
            options={HANDLES.map((h) => ({ value: h, label: t(`ed.handle.${h}`) }))} /></Section>
          <Section title={t('ed.sec.material')}><div className="space-y-3">
            <Select label={t('ed.board')} value={doc.materialId} onChange={(e) => pickMaterial(e.target.value)} options={matOpts} />
            <div className="grid grid-cols-2 gap-3"><Select label={t('ed.backMaterial')} value={doc.input.back_material ?? 'HDF'} onChange={(e) => setInput({ back_material: e.target.value })} options={BACKS.map((b) => ({ value: b, label: b }))} />
              <NumberField label={t('ed.backThickness')} unit="mm" step={0.5} min={3} max={8} value={doc.input.back_thickness ?? 4} onChange={(n) => setInput({ back_thickness: n })} error={errs.back_thickness} /></div></div></Section>
          <Section title={t('ed.sec.colors')}><ColorsPanel colors={doc.colors} onChange={(c) => set({ colors: c })} /></Section>
          <Section title={t('ed.sec.parts')}>{geo.data ? <ComponentList boxes={geo.data.boxes} selected={selName} onSelect={setSelName} /> : <Skeleton className="h-24" />}</Section>
          <Section title={t('ed.sec.selected')}><ComponentProperties box={sel} colors={doc.colors} onColor={(g, c) => set({ colors: { ...doc.colors, [g]: c } })} /></Section>
          <Section title={t('ed.sec.project')}><Select label={t('calc.attach')} value={doc.projectId} onChange={(e) => set({ projectId: e.target.value })} options={[{ value: '', label: t('calc.none') }, ...(projects.data?.results.map((p) => ({ value: p.id, label: p.name })) ?? [])]} /></Section>
          {!!geo.data?.warnings.length && <Section title={t('calc.warnings')}><ul className="space-y-1.5 text-xs text-warning">{geo.data.warnings.map((w) => <li key={w}>{w}</li>)}</ul></Section>}
        </aside>
      </div>

      <footer className="flex flex-wrap items-center gap-x-6 gap-y-3 border-t border-line bg-sidebar px-4 py-3 text-sm sm:px-6">
        <div className="flex gap-5"><span><span className="text-muted">{t('calc.panels')} </span><span className="num font-medium">{s?.panel_count ?? '-'}</span></span><span><span className="text-muted">{t('calc.area')} </span><span className="num font-medium">{s ? `${s.total_area_m2} m2` : '-'}</span></span><span><span className="text-muted">{t('calc.edge')} </span><span className="num font-medium">{s ? `${s.edge_banding_m} m` : '-'}</span></span></div>
        <div className="ml-auto flex flex-wrap items-center gap-2"><Download size={15} className="text-muted" aria-hidden /><span className="sr-only">{t('calc.export')}</span>
          {['glb', 'gltf', 'obj'].map((f) => <Button key={f} size="sm" variant="secondary" disabled={blocked} onClick={() => exp3d(f)}>{f.toUpperCase()}</Button>)}
          <Button size="sm" variant="secondary" icon={<FileText size={14} />} loading={expCut.isPending && expCut.variables === 'pdf'} disabled={!calc.data} onClick={() => expCut.mutate('pdf')}>{t('ed.cutPdf')}</Button>
          <Button size="sm" variant="secondary" icon={<FileSpreadsheet size={14} />} loading={expCut.isPending && expCut.variables === 'xlsx'} disabled={!calc.data} onClick={() => expCut.mutate('xlsx')}>{t('ed.cutXlsx')}</Button></div>
      </footer>
      <ConfirmDialog open={!!replace} onClose={() => setReplace(null)} title={t('ed.replaceTitle')} message={t('ed.replaceMsg')} confirmLabel={t('ed.replaceDo')} cancelLabel={t('common.cancel')} onConfirm={() => replace && applyTemplate(replace)} />
    </div>
  )
}
