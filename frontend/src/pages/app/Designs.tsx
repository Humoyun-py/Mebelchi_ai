import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Box, Copy, Sofa, Trash2 } from 'lucide-react'
import { api, apiError } from '../../lib/api'
import { fmtAgo } from '../../lib/format'
import type { Design, Page } from '../../lib/types'
import { Button } from '../../components/ui/Button'
import { HoverCard } from '../../components/ui/Card'
import { Tabs } from '../../components/ui/Tabs'
import { ConfirmDialog } from '../../components/ui/Modal'
import { EmptyState, ErrorState, Skeleton } from '../../components/ui/Misc'
import { toast } from '../../components/ui/Toast'
import { useT } from '../../lib/i18n'

export default function Designs() {
  const t = useT(); const nav = useNavigate(); const qc = useQueryClient(); const [kind, setKind] = useState<'' | 'furniture' | 'interior'>(''); const [del, setDel] = useState<Design | null>(null)
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ['designs', kind], queryFn: async () => (await api.get<Page<Design>>('/designs/', { params: kind ? { kind } : {} })).data })
  const dup = useMutation({ mutationFn: async (d: Design) => (await api.post<Design>(`/designs/${d.id}/duplicate/`)).data, onSuccess: () => { toast.success(t('designs.duplicated')); qc.invalidateQueries({ queryKey: ['designs'] }); qc.invalidateQueries({ queryKey: ['summary'] }) }, onError: (e) => toast.error(apiError(e).message) })
  const rm = useMutation({ mutationFn: (d: Design) => api.delete(`/designs/${d.id}/`), onSuccess: () => { setDel(null); qc.invalidateQueries({ queryKey: ['designs'] }); qc.invalidateQueries({ queryKey: ['summary'] }); toast.success('Deleted') }, onError: (e) => toast.error(apiError(e).message) })
  return (
    <div className="mx-auto max-w-5xl p-4 sm:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="text-2xl font-bold">3D models and designs</h1><Link to="/app/editor"><Button icon={<Box size={16} />}>New design</Button></Link></div>
      <div className="mt-5"><Tabs tabs={[{ id: '', label: 'All' }, { id: 'furniture', label: 'Furniture' }, { id: 'interior', label: 'Interior' }]} value={kind} onChange={setKind} /></div>
      <div className="mt-5">{isLoading ? <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-28" />)}</div> : isError ? <ErrorState message="Could not load designs." onRetry={refetch} />
        : data?.results.length ? <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{data.results.map((d) => { const cab = (d.config as { input?: { width: number; height: number; depth: number } }).input; return (
          <HoverCard key={d.id} className="p-4" as="div"><button onClick={() => nav(d.room_flow ? `/app/rooms/${d.room_flow}` : d.kind === 'interior' ? `/app/interior?design=${d.id}` : `/app/editor?design=${d.id}`)} className="block w-full text-left"><span className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/15 text-primary">{d.kind === 'interior' ? <Sofa size={20} /> : <Box size={20} />}</span>
            <span className="block font-medium">{d.name}</span><span className="num mt-1 block text-xs text-muted">{cab ? `${cab.width} x ${cab.height} x ${cab.depth} mm · ` : ''}{d.kind} · {fmtAgo(d.updated_at)}</span></button>
            <button aria-label={`${t('designs.duplicate')}: ${d.name}`} onClick={() => dup.mutate(d)} disabled={dup.isPending} className="mt-3 rounded-md p-1.5 text-muted hover:bg-card2 hover:text-fg disabled:opacity-50"><Copy size={15} /></button>
            <button aria-label={`Delete ${d.name}`} onClick={() => setDel(d)} className="mt-3 rounded-md p-1.5 text-muted hover:bg-danger/10 hover:text-danger"><Trash2 size={15} /></button></HoverCard>) })}</div>
          : <EmptyState icon={<Box size={22} />} title="No saved designs" text="Save a design from the furniture editor or interior designer." action={<Link to="/app/editor"><Button>Open editor</Button></Link>} />}</div>
      <ConfirmDialog open={!!del} onClose={() => setDel(null)} title="Delete design" message={`"${del?.name}" will be permanently deleted.`} loading={rm.isPending} onConfirm={() => del && rm.mutate(del)} />
    </div>
  )
}
