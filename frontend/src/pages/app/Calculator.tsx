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
import { useL, useT } from '../../lib/i18n'
import { PanelSection, RightPanel } from '../../layouts/RightPanel'
import type { CabinetInput, CuttingList } from '../../lib/types'

export default function Calculator() {
  const L = useL(); const t = useT(); const meta = useMeta()
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
    onSuccess: () => { toast.success(t('calc.saved')); qc.invalidateQueries({ queryKey: ['summary'] }); qc.invalidateQueries({ queryKey: ['project-calcs'] }) }, onError: (e) => toast.error(apiError(e).message) })
  const toList = useMutation({
    mutationFn: async () => (await api.post<CuttingList>('/cutting-lists/from-calculation/', { ...full, name: `Cabinet ${input.width}x${input.height}x${input.depth}`, ...(projectId ? { project: Number(projectId) } : {}) })).data,
    onSuccess: (l) => { toast.success(t('calc.listCreated')); qc.invalidateQueries({ queryKey: ['summary'] }); nav(`/app/cutting-lists/${l.id}`) }, onError: (e) => toast.error(apiError(e).message) })
  const exp3d = async (fmt: string) => { try { await downloadBlob(`/geometry/export/${fmt}/`, `mebelchi-cabinet.${fmt}`, 'post', full) } catch (e) { toast.error(apiError(e).message) } }
  const r = calc.data
  const hwName = (n: string) => { const k = 'hw.' + n; const v = t(k); return v === k ? n : v }
  return (
    <div className="mx-auto max-w-6xl p-4 sm:p-8">
      <h1 className="text-2xl font-bold">{t('side.calc')}</h1><p className="mt-1 text-sm text-muted">{t('calc.sub')}</p>
      <div className="mt-6 grid gap-5 lg:grid-cols-[19rem_1fr]">
        <Card className="h-fit space-y-4 p-4">
          <CabinetForm value={input} onChange={setInput} errors={errors} />
          <Select label={t('calc.board')} value={material} onChange={(e) => setMaterial(e.target.value)} options={(meta.data?.boards ?? []).map((b) => ({ value: b.value, label: L(b.label) }))} />
          <Select label={t('calc.attach')} value={projectId} onChange={(e) => setProjectId(e.target.value)} options={[{ value: '', label: t('calc.none') }, ...(projects.data?.results.map((p) => ({ value: p.id, label: p.name })) ?? [])]} />
          <div className="grid gap-2 pt-1">
            <Button icon={<Save size={16} />} variant="secondary" loading={save.isPending} disabled={!r} onClick={() => save.mutate()}>{t('calc.save')}</Button>
            <Button icon={<Scissors size={16} />} loading={toList.isPending} disabled={!r} onClick={() => toList.mutate()}>{t('calc.toList')}</Button>
          </div>
        </Card>
        <div className="min-w-0 space-y-4">
          {Object.keys(errors).length > 0 && <p role="alert" className="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger">{Object.values(errors)[0]}</p>}
          {calc.isError && !Object.keys(errors).length && <p role="alert" className="text-sm text-danger">{apiError(calc.error).message}</p>}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label={t('calc.panels')} value={r?.summary.panel_count ?? '-'} /><Stat label={t('calc.area')} value={r ? `${r.summary.total_area_m2.toFixed(2)} m2` : '-'} />
            <Stat label={t('calc.edge')} value={r ? `${r.summary.edge_banding_m} m` : '-'} /><Stat label={t('calc.types')} value={r?.summary.distinct_parts ?? '-'} /></div>
          <Tabs tabs={[{ id: 'parts', label: t('calc.parts'), icon: <FileText size={15} /> }, { id: '3d', label: t('calc.preview'), icon: <Box size={15} /> }]} value={tab} onChange={setTab} />
          {tab === 'parts' ? (r ? <PartsTable parts={r.parts} /> : <Skeleton className="h-64" />)
            : geo.data ? <div className="space-y-3"><CabinetViewer boxes={geo.data.boxes} dims={geo.data.dimensions} className="h-[min(60vh,460px)]" />
              <div className="flex flex-wrap gap-2"><span className="self-center text-sm text-muted">{t('calc.export')}</span>{['glb', 'gltf', 'obj'].map((f) => <Button key={f} size="sm" variant="secondary" onClick={() => exp3d(f)}>{f.toUpperCase()}</Button>)}</div></div> : <Skeleton className="h-[420px]" />}
          <p className="text-xs text-muted">{r?.disclaimer ?? t('calc.disclaimer')}</p>
        </div>
      </div>
      <RightPanel>
        <PanelSection title={t('calc.summary')}>{r ? <ul className="space-y-2 text-sm">{Object.entries(r.summary.by_material).map(([k, m]) => <li key={k} className="flex justify-between gap-2"><span>{k}</span><span className="num text-muted">{m.area_m2} m2</span></li>)}</ul> : <Skeleton className="h-16" />}
          {r && <p className="mt-3 text-xs text-muted">{t('calc.waste').replace('{n}', String(Math.round(r.summary.waste_factor_assumed * 100)))}</p>}</PanelSection>
        {!!r?.warnings.length && <PanelSection title={t('calc.warnings')}><ul className="space-y-2">{r.warnings.map((w) => <li key={w} className="flex gap-2 text-xs text-warning"><AlertTriangle size={14} className="mt-0.5 shrink-0" />{w}</li>)}</ul></PanelSection>}
        {!!r?.hardware?.length && <PanelSection title={t('calc.hardware')}><ul className="space-y-1.5 text-sm">{r.hardware.map((h) => <li key={h.name} title={h.note} className="flex justify-between gap-2"><span>{hwName(h.name)}</span><span className="num text-muted">{h.quantity}</span></li>)}</ul><p className="mt-2 text-xs text-muted">{t('calc.hwNote')}</p></PanelSection>}
        <PanelSection title={t('calc.assumptions')}><ul className="list-disc space-y-1.5 pl-4 text-xs text-muted">{r?.assumptions.map((a) => <li key={a}>{a}</li>)}</ul></PanelSection>
      </RightPanel>
    </div>
  )
}
