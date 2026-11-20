import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Calculator, Image as ImageIcon, Pin, Ruler, Save, Scissors, Trash2 } from 'lucide-react'
import { api, apiError } from '../../lib/api'
import { fmtAgo } from '../../lib/format'
import type { CalcResult, CuttingList, Design, Project } from '../../lib/types'
import { Button } from '../../components/ui/Button'
import { Card, SectionTitle } from '../../components/ui/Card'
import { Input, NumberField, Textarea } from '../../components/ui/Field'
import { ConfirmDialog } from '../../components/ui/Modal'
import { Breadcrumbs, EmptyState, ErrorState, Skeleton } from '../../components/ui/Misc'
import { toast } from '../../components/ui/Toast'
import { PanelSection, RightPanel } from '../../layouts/RightPanel'

export default function ProjectDetail() {
  const { id } = useParams(); const nav = useNavigate(); const qc = useQueryClient()
  const proj = useQuery({ queryKey: ['project', id], queryFn: async () => (await api.get<Project>(`/projects/${id}/`)).data })
  const acts = useQuery({ queryKey: ['project-activity', id], queryFn: async () => (await api.get<{ id: number; action: string; detail: string; created_at: string }[]>(`/projects/${id}/activity/`)).data })
  const calcs = useQuery({ queryKey: ['project-calcs', id], queryFn: async () => (await api.get<{ results: { id: number; name: string; result: CalcResult }[] }>('/calculations/', { params: { project: id } })).data })
  const lists = useQuery({ queryKey: ['project-lists', id], queryFn: async () => (await api.get<{ results: CuttingList[] }>('/cutting-lists/', { params: { project: id } })).data })
  const designs = useQuery({ queryKey: ['project-designs', id], queryFn: async () => (await api.get<{ results: Design[] }>('/designs/', { params: { project: id } })).data })
  const [f, setF] = useState({ name: '', description: '', width: NaN, height: NaN, depth: NaN }); const [del, setDel] = useState(false)
  useEffect(() => { const p = proj.data; if (p) setF({ name: p.name, description: p.description, width: p.width ?? NaN, height: p.height ?? NaN, depth: p.depth ?? NaN }) }, [proj.data])
  const save = useMutation({
    mutationFn: () => api.patch(`/projects/${id}/`, { name: f.name.trim(), description: f.description, width: Number.isNaN(f.width) ? null : f.width, height: Number.isNaN(f.height) ? null : f.height, depth: Number.isNaN(f.depth) ? null : f.depth }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['project', id] }); qc.invalidateQueries({ queryKey: ['projects'] }); qc.invalidateQueries({ queryKey: ['project-activity', id] }); toast.success('Project saved') },
    onError: (e) => toast.error(apiError(e).message),
  })
  const remove = useMutation({ mutationFn: () => api.delete(`/projects/${id}/`), onSuccess: () => { qc.invalidateQueries({ queryKey: ['projects'] }); toast.success('Project deleted'); nav('/app/projects') }, onError: (e) => toast.error(apiError(e).message) })
  const pin = useMutation({ mutationFn: () => api.post(`/projects/${id}/pin/`), onSuccess: () => { qc.invalidateQueries({ queryKey: ['project', id] }); qc.invalidateQueries({ queryKey: ['projects'] }) } })

  if (proj.isLoading) return <div className="p-8"><Skeleton className="h-96" /></div>
  if (proj.isError || !proj.data) return <div className="p-8"><ErrorState message="Project not found." onRetry={() => nav('/app/projects')} /></div>
  const p = proj.data; const q = `?project=${p.id}`
  return (
    <div className="mx-auto max-w-4xl space-y-8 p-4 sm:p-8">
      <Breadcrumbs items={[{ label: 'Projects', to: '/app/projects' }, { label: p.name }]} />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h1 className="text-2xl font-bold">{p.name}</h1><p className="mt-1 text-sm capitalize text-muted">{p.category.replace('_', ' ')} · {p.status}</p></div>
        <div className="flex gap-2"><Button variant="secondary" icon={<Pin size={16} />} onClick={() => pin.mutate()}>{p.pinned ? 'Unpin' : 'Pin'}</Button>
          <Button variant="danger" icon={<Trash2 size={16} />} onClick={() => setDel(true)}>Delete</Button></div>
      </div>
      <Card className="space-y-4 p-5">
        <Input label="Name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} maxLength={160} />
        <Textarea label="Description" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
        <div className="grid grid-cols-3 gap-3"><NumberField label="Width" unit="mm" value={f.width} onChange={(n) => setF({ ...f, width: n })} /><NumberField label="Height" unit="mm" value={f.height} onChange={(n) => setF({ ...f, height: n })} /><NumberField label="Depth" unit="mm" value={f.depth} onChange={(n) => setF({ ...f, depth: n })} /></div>
        <div className="flex justify-end"><Button icon={<Save size={16} />} loading={save.isPending} disabled={!f.name.trim()} onClick={() => save.mutate()}>Save changes</Button></div>
      </Card>
      <section><SectionTitle title="Work in this project" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[[Calculator, 'Calculator', `/app/calculator${q}`], [Scissors, 'Cutting lists', `/app/cutting-lists${q}`], [Ruler, 'Editor', `/app/editor${q}`], [ImageIcon, 'Gallery', `/app/gallery${q}`]].map(([Icon, l, to]) => {
            const I = Icon as typeof Calculator; return <Link key={l as string} to={to as string} className="flex items-center gap-2 rounded-[14px] border border-line bg-card p-4 text-sm font-medium transition-colors hover:border-primary/50 hover:bg-card2"><I size={18} className="text-primary" />{l as string}</Link> })}
        </div></section>
      <section><SectionTitle title="Saved calculations" />
        {calcs.data?.results.length ? <ul className="divide-y divide-line rounded-[14px] border border-line bg-card">{calcs.data.results.map((c) => <li key={c.id} className="flex items-center justify-between px-4 py-3 text-sm"><span>{c.name}</span><span className="num text-muted">{c.result.summary.total_area_m2} m2 · {c.result.summary.panel_count} panels</span></li>)}</ul>
          : <EmptyState icon={<Calculator size={22} />} title="No saved calculations" text="Save a calculation from the calculator to attach it here." />}</section>
      <section><SectionTitle title="Cutting lists" />
        {lists.data?.results.length ? <ul className="divide-y divide-line rounded-[14px] border border-line bg-card">{lists.data.results.map((l) => <li key={l.id}><Link to={`/app/cutting-lists/${l.id}`} className="flex items-center justify-between px-4 py-3 text-sm hover:bg-card2"><span>{l.name}</span><span className="num text-muted">{l.totals.pieces} pieces · {l.totals.area_m2} m2</span></Link></li>)}</ul>
          : <EmptyState icon={<Scissors size={22} />} title="No cutting lists" />}</section>
      <section><SectionTitle title="Designs" />
        {designs.data?.results.length ? <ul className="divide-y divide-line rounded-[14px] border border-line bg-card">{designs.data.results.map((d) => <li key={d.id} className="flex items-center justify-between px-4 py-3 text-sm"><span>{d.name}</span><span className="text-muted">{d.kind} · {fmtAgo(d.updated_at)}</span></li>)}</ul>
          : <EmptyState icon={<Ruler size={22} />} title="No designs yet" />}</section>
      <ConfirmDialog open={del} onClose={() => setDel(false)} title="Delete project" message="This permanently deletes the project and its calculations, cutting lists and designs." loading={remove.isPending} onConfirm={() => remove.mutate()} />
      <RightPanel>
        <PanelSection title="Project information"><dl className="space-y-2 text-sm">{[['Category', p.category.replace('_', ' ')], ['Status', p.status], ['Created', fmtAgo(p.created_at)], ['Updated', fmtAgo(p.updated_at)]].map(([k, v]) => <div key={k} className="flex justify-between"><dt className="text-muted">{k}</dt><dd className="capitalize">{v}</dd></div>)}</dl></PanelSection>
        <PanelSection title="Dimensions"><p className="num text-sm">{p.width ? `${p.width} x ${p.height ?? '-'} x ${p.depth ?? '-'} mm` : 'Not set'}</p></PanelSection>
        <PanelSection title="Contents"><dl className="space-y-1.5 text-sm">{Object.entries(p.counts).map(([k, v]) => <div key={k} className="flex justify-between"><dt className="capitalize text-muted">{k.replace('_', ' ')}</dt><dd className="num">{v}</dd></div>)}</dl></PanelSection>
        <PanelSection title="Recent activity">{acts.data?.length ? <ul className="space-y-2 text-xs">{acts.data.slice(0, 8).map((a) => <li key={a.id}><span className="capitalize">{a.action}</span>{a.detail && <span className="text-muted"> · {a.detail}</span>}<span className="block text-muted">{fmtAgo(a.created_at)}</span></li>)}</ul> : <p className="text-xs text-muted">No activity yet.</p>}</PanelSection>
      </RightPanel>
    </div>
  )
}
