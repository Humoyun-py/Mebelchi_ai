import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Box, FileText, Save, Scissors } from 'lucide-react'
import { api, apiError, downloadBlob } from '../../lib/api'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Select } from '../../components/ui/Field'
import { Tabs } from '../../components/ui/Tabs'
import { Skeleton, Stat } from '../../components/ui/Misc'
import { toast } from '../../components/ui/Toast'
import { CabinetViewer } from '../../components/three/LazyViewer'
import { CabinetForm, DEFAULT_INPUT, PartsTable } from '../../components/CabinetPanel'
import { useCalculation, useGeometry, useMeta, useProjects } from '../../hooks/queries'
import { useL } from '../../lib/i18n'
import { PanelSection, RightPanel } from '../../layouts/RightPanel'
import type { CabinetInput, CuttingList } from '../../lib/types'

export default function Calculator() {
  const L = useL(); const meta = useMeta()
  const nav = useNavigate(); const qc = useQueryClient(); const [params] = useSearchParams()
  const [input, setInput] = useState<CabinetInput>(() => ({ ...DEFAULT_INPUT })); const [material, setMaterial] = useState('MDF'); const [tab, setTab] = useState<'parts' | '3d'>('parts')
  const [projectId, setProjectId] = useState(params.get('project') ?? '')
  const full = { ...input, material }
  const valid = Object.values(input).every(Number.isFinite)
  const calc = useCalculation(full, valid); const geo = useGeometry(full, undefined, valid && tab === '3d')
  const errors = calc.isError ? apiError(calc.error).fields : {}
  const projects = useProjects({ page_size: 100 })
  const save = useMutation({
    mutationFn: async () => (await api.post('/calculations/material/', { ...full, save: true, name: `Cabinet ${input.width}x${input.height}x${input.depth}`, ...(projectId ? { project: Number(projectId) } : {}) })).data,
    onSuccess: () => { toast.success('Calculation saved'); qc.invalidateQueries({ queryKey: ['summary'] }); qc.invalidateQueries({ queryKey: ['project-calcs'] }) }, onError: (e) => toast.error(apiError(e).message) })
  const toList = useMutation({
    mutationFn: async () => (await api.post<CuttingList>('/cutting-lists/from-calculation/', { ...full, name: `Cabinet ${input.width}x${input.height}x${input.depth}`, ...(projectId ? { project: Number(projectId) } : {}) })).data,
    onSuccess: (l) => { toast.success('Cutting list created'); qc.invalidateQueries({ queryKey: ['summary'] }); nav(`/app/cutting-lists/${l.id}`) }, onError: (e) => toast.error(apiError(e).message) })
  const exp3d = async (fmt: string) => { try { await downloadBlob(`/geometry/export/${fmt}/`, `mebelchi-cabinet.${fmt}`, 'post', full) } catch (e) { toast.error(apiError(e).message) } }
  const r = calc.data
  return (
    <div className="mx-auto max-w-6xl p-4 sm:p-8">
      <h1 className="text-2xl font-bold">Material calculator</h1><p className="mt-1 text-sm text-muted">Enter cabinet dimensions in millimetres. Results update as you type.</p>
      <div className="mt-6 grid gap-5 lg:grid-cols-[19rem_1fr]">
        <Card className="h-fit space-y-4 p-4">
          <CabinetForm value={input} onChange={setInput} errors={errors} />
          <Select label="Board material" value={material} onChange={(e) => setMaterial(e.target.value)} options={(meta.data?.boards ?? []).map((b) => ({ value: b.value, label: L(b.label) }))} />
          <Select label="Attach to project" value={projectId} onChange={(e) => setProjectId(e.target.value)} options={[{ value: '', label: 'None' }, ...(projects.data?.results.map((p) => ({ value: p.id, label: p.name })) ?? [])]} />
          <div className="grid gap-2 pt-1">
            <Button icon={<Save size={16} />} variant="secondary" loading={save.isPending} disabled={!r} onClick={() => save.mutate()}>Save calculation</Button>
            <Button icon={<Scissors size={16} />} loading={toList.isPending} disabled={!r} onClick={() => toList.mutate()}>Create cutting list</Button>
          </div>
        </Card>
        <div className="min-w-0 space-y-4">
          {Object.keys(errors).length > 0 && <p role="alert" className="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger">{Object.values(errors)[0]}</p>}
          {calc.isError && !Object.keys(errors).length && <p role="alert" className="text-sm text-danger">{apiError(calc.error).message}</p>}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Panels" value={r?.summary.panel_count ?? '-'} /><Stat label="Total area" value={r ? `${r.summary.total_area_m2} m2` : '-'} />
            <Stat label="Edge banding" value={r ? `${r.summary.edge_banding_m} m` : '-'} /><Stat label="Part types" value={r?.summary.distinct_parts ?? '-'} /></div>
          <Tabs tabs={[{ id: 'parts', label: 'Parts', icon: <FileText size={15} /> }, { id: '3d', label: '3D preview', icon: <Box size={15} /> }]} value={tab} onChange={setTab} />
          {tab === 'parts' ? (r ? <PartsTable parts={r.parts} /> : <Skeleton className="h-64" />)
            : geo.data ? <div className="space-y-3"><CabinetViewer boxes={geo.data.boxes} dims={geo.data.dimensions} className="h-[min(60vh,460px)]" />
              <div className="flex flex-wrap gap-2"><span className="self-center text-sm text-muted">Export model:</span>{['glb', 'gltf', 'obj'].map((f) => <Button key={f} size="sm" variant="secondary" onClick={() => exp3d(f)}>{f.toUpperCase()}</Button>)}</div></div> : <Skeleton className="h-[420px]" />}
          <p className="text-xs text-muted">{r?.disclaimer ?? 'Calculated output for professional review. Not verified for manufacture.'}</p>
        </div>
      </div>
      <RightPanel>
        <PanelSection title="Material summary">{r ? <ul className="space-y-2 text-sm">{Object.entries(r.summary.by_material).map(([k, m]) => <li key={k} className="flex justify-between gap-2"><span>{k}</span><span className="num text-muted">{m.area_m2} m2</span></li>)}</ul> : <Skeleton className="h-16" />}
          {r && <p className="mt-3 text-xs text-muted">Add about {Math.round(r.summary.waste_factor_assumed * 100)}% for waste. Use the optimizer for an exact sheet count.</p>}</PanelSection>
        {!!r?.warnings.length && <PanelSection title="Warnings"><ul className="space-y-2">{r.warnings.map((w) => <li key={w} className="flex gap-2 text-xs text-warning"><AlertTriangle size={14} className="mt-0.5 shrink-0" />{w}</li>)}</ul></PanelSection>}
        <PanelSection title="Assumptions"><ul className="list-disc space-y-1.5 pl-4 text-xs text-muted">{r?.assumptions.map((a) => <li key={a}>{a}</li>)}</ul></PanelSection>
      </RightPanel>
    </div>
  )
}
