import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Download, Heart, ImageIcon, Maximize2, Pencil, Trash2, X } from 'lucide-react'
import clsx from 'clsx'
import { api, apiError } from '../../lib/api'
import { fmtBytes } from '../../lib/format'
import type { GalleryImage, Page } from '../../lib/types'
import { Button } from '../../components/ui/Button'
import { ContextMenu } from '../../components/ui/Dropdown'
import { FileUploader } from '../../components/ui/FileUploader'
import { Input, Select } from '../../components/ui/Field'
import { ConfirmDialog, Modal } from '../../components/ui/Modal'
import { EmptyState, ErrorState, Pagination, Skeleton } from '../../components/ui/Misc'
import { toast } from '../../components/ui/Toast'
import { useDebounced } from '../../hooks/queries'

const SOURCES = [['', 'All sources'], ['upload', 'Uploads'], ['room', 'Room photos'], ['sketch', 'Hand sketches'], ['drawing', 'Drawings'], ['render', 'Renders']]

export default function Gallery() {
  const [params] = useSearchParams(); const qc = useQueryClient()
  const [q, setQ] = useState(''); const [fav, setFav] = useState(false); const [source, setSource] = useState(params.get('source') ?? ''); const [page, setPage] = useState(1); const dq = useDebounced(q, 300)
  const [view, setView] = useState<number | null>(null); const [ren, setRen] = useState<GalleryImage | null>(null); const [name, setName] = useState(''); const [del, setDel] = useState<GalleryImage | null>(null)
  const query = { search: dq, page, ...(fav ? { favorite: true } : {}), ...(source ? { source } : {}), ...(params.get('project') ? { project: params.get('project')! } : {}) }
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ['gallery', query], queryFn: async () => (await api.get<Page<GalleryImage>>('/gallery/', { params: query })).data })
  const inval = () => { qc.invalidateQueries({ queryKey: ['gallery'] }); qc.invalidateQueries({ queryKey: ['summary'] }); qc.invalidateQueries({ queryKey: ['usage'] }) }
  const upload = useMutation({ mutationFn: async (files: File[]) => { for (const f of files) { const fd = new FormData(); fd.append('image', f); fd.append('source', source || 'upload'); if (params.get('project')) fd.append('project', params.get('project')!); await api.post('/gallery/', fd) } },
    onSuccess: () => { toast.success('Uploaded'); inval() }, onError: (e) => { toast.error(apiError(e).message); inval() } })
  const favM = useMutation({ mutationFn: (i: GalleryImage) => api.post(`/gallery/${i.id}/favorite/`), onSuccess: inval })
  const renM = useMutation({ mutationFn: () => api.patch(`/gallery/${ren!.id}/`, { name: name.trim() }), onSuccess: () => { setRen(null); inval(); toast.success('Renamed') }, onError: (e) => toast.error(apiError(e).message) })
  const delM = useMutation({ mutationFn: (i: GalleryImage) => api.delete(`/gallery/${i.id}/`), onSuccess: () => { setDel(null); setView(null); inval(); toast.success('Deleted') } })
  const items = data?.results ?? []; const cur = view !== null ? items[view] : null
  useEffect(() => {
    if (view === null) return
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') setView(null); if (e.key === 'ArrowRight') setView((v) => (v !== null && v < items.length - 1 ? v + 1 : v)); if (e.key === 'ArrowLeft') setView((v) => (v !== null && v > 0 ? v - 1 : v)) }
    document.addEventListener('keydown', k); return () => document.removeEventListener('keydown', k)
  }, [view, items.length])
  const download = (i: GalleryImage) => { window.location.href = i.url + '&download=1' }
  return (
    <div className="mx-auto max-w-6xl p-4 sm:p-8">
      <h1 className="text-2xl font-bold">Images</h1><p className="mt-1 text-sm text-muted">Room photos, sketches, drawings and renders stored privately in your account.</p>
      <div className="mt-5"><FileUploader accept="image/png,image/jpeg,image/webp" multiple maxMB={10} onFiles={(f) => upload.mutate(f)} disabled={upload.isPending} label={upload.isPending ? 'Uploading...' : 'Drop images here or click to browse'} /></div>
      <div className="mt-5 flex flex-wrap items-end gap-3">
        <div className="min-w-48 flex-1 sm:max-w-xs"><Input label="Search images" value={q} onChange={(e) => { setQ(e.target.value); setPage(1) }} /></div>
        <div className="w-44"><Select label="Source" value={source} onChange={(e) => { setSource(e.target.value); setPage(1) }} options={SOURCES.map(([value, label]) => ({ value, label }))} /></div>
        <Button variant={fav ? 'primary' : 'secondary'} aria-pressed={fav} icon={<Heart size={16} />} onClick={() => { setFav(!fav); setPage(1) }}>Favorites</Button></div>
      <div className="mt-5">
        {isLoading ? <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">{[0, 1, 2, 3, 4, 5, 6, 7].map((i) => <Skeleton key={i} className="h-44" />)}</div>
          : isError ? <ErrorState message="Could not load images." onRetry={refetch} />
          : items.length ? <div className="columns-2 gap-3 md:columns-3 lg:columns-4">{items.map((i, idx) => (
            <ContextMenu key={i.id} className="mb-3 break-inside-avoid" items={[{ label: 'Open', icon: <Maximize2 size={16} />, onClick: () => setView(idx) }, { label: i.favorite ? 'Remove favorite' : 'Favorite', icon: <Heart size={16} />, onClick: () => favM.mutate(i) }, { label: 'Rename', icon: <Pencil size={16} />, onClick: () => { setRen(i); setName(i.name) } }, { label: 'Download', icon: <Download size={16} />, onClick: () => download(i) }, { label: 'Delete', icon: <Trash2 size={16} />, danger: true, onClick: () => setDel(i) }]}>
              <div className="group relative overflow-hidden rounded-xl border border-line bg-card"><button onClick={() => setView(idx)} className="block w-full" aria-label={`Open ${i.name}`}><img src={i.url} alt={i.name} loading="lazy" className="w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]" style={{ aspectRatio: i.width && i.height ? `${i.width}/${i.height}` : undefined }} /></button>
                <div className="absolute inset-x-0 bottom-0 flex items-center justify-between bg-gradient-to-t from-black/70 to-transparent p-2 text-xs text-white opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100"><span className="truncate">{i.name}</span>
                  <button onClick={() => favM.mutate(i)} aria-label={i.favorite ? 'Remove from favorites' : 'Add to favorites'} aria-pressed={i.favorite}><Heart size={16} className={clsx(i.favorite && 'fill-red-500 text-red-500')} /></button></div>
                {i.favorite && <Heart size={16} className="absolute right-2 top-2 fill-red-500 text-red-500 group-hover:hidden" aria-hidden />}</div></ContextMenu>))}</div>
          : <EmptyState icon={<ImageIcon size={22} />} title="No images found" text={q || fav || source ? 'Try clearing the filters.' : 'Upload your first image above.'} />}
        {data && <Pagination page={page} count={data.count} pageSize={24} onPage={setPage} />}
      </div>
      {cur && (
        <div className="fixed inset-0 z-50 flex flex-col bg-black/90" role="dialog" aria-modal="true" aria-label={cur.name}>
          <div className="flex items-center justify-between p-3 text-white"><div className="min-w-0"><p className="truncate text-sm font-medium">{cur.name}</p><p className="num text-xs text-white/60">{cur.width} x {cur.height} · {fmtBytes(cur.size_bytes)}</p></div>
            <div className="flex gap-1">{[[Heart, 'Favorite', () => favM.mutate(cur)], [Download, 'Download', () => download(cur)], [Pencil, 'Rename', () => { setRen(cur); setName(cur.name) }], [Trash2, 'Delete', () => setDel(cur)], [X, 'Close', () => setView(null)]].map(([I, l, fn]) => { const Icon = I as typeof Heart; return <button key={l as string} aria-label={l as string} onClick={fn as () => void} className="rounded-lg p-2 hover:bg-white/10"><Icon size={20} className={clsx(l === 'Favorite' && cur.favorite && 'fill-red-500 text-red-500')} /></button> })}</div></div>
          <div className="relative flex min-h-0 flex-1 items-center justify-center p-4"><img src={cur.url} alt={cur.name} className="max-h-full max-w-full object-contain" />
            {view! > 0 && <button aria-label="Previous image" onClick={() => setView(view! - 1)} className="absolute left-2 rounded-full bg-black/50 p-2 text-white hover:bg-black/70"><ChevronLeft size={24} /></button>}
            {view! < items.length - 1 && <button aria-label="Next image" onClick={() => setView(view! + 1)} className="absolute right-2 rounded-full bg-black/50 p-2 text-white hover:bg-black/70"><ChevronRight size={24} /></button>}</div></div>)}
      <Modal open={!!ren} onClose={() => setRen(null)} title="Rename image" footer={<><Button variant="ghost" onClick={() => setRen(null)}>Cancel</Button><Button loading={renM.isPending} disabled={!name.trim()} onClick={() => renM.mutate()}>Save</Button></>}><Input label="Name" value={name} onChange={(e) => setName(e.target.value)} maxLength={160} /></Modal>
      <ConfirmDialog open={!!del} onClose={() => setDel(null)} title="Delete image" message={`"${del?.name}" will be permanently deleted.`} loading={delM.isPending} onConfirm={() => del && delM.mutate(del)} />
    </div>
  )
}
