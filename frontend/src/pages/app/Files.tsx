import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, FileText, Pencil, Trash2 } from 'lucide-react'
import { api, apiError } from '../../lib/api'
import { fmtAgo, fmtBytes } from '../../lib/format'
import type { Page, UserFile } from '../../lib/types'
import { Button } from '../../components/ui/Button'
import { FileUploader } from '../../components/ui/FileUploader'
import { Input, Select } from '../../components/ui/Field'
import { ConfirmDialog, Modal } from '../../components/ui/Modal'
import { Badge, type Column, DataTable, EmptyState, ErrorState, Pagination, Skeleton } from '../../components/ui/Misc'
import { toast } from '../../components/ui/Toast'
import { useDebounced } from '../../hooks/queries'

export default function Files() {
  const qc = useQueryClient(); const [q, setQ] = useState(''); const [kind, setKind] = useState(''); const [page, setPage] = useState(1); const dq = useDebounced(q, 300)
  const [ren, setRen] = useState<UserFile | null>(null); const [name, setName] = useState(''); const [del, setDel] = useState<UserFile | null>(null)
  const query = { search: dq, page, ...(kind ? { kind } : {}) }
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ['files', query], queryFn: async () => (await api.get<Page<UserFile>>('/files/', { params: query })).data })
  const inval = () => { qc.invalidateQueries({ queryKey: ['files'] }); qc.invalidateQueries({ queryKey: ['summary'] }); qc.invalidateQueries({ queryKey: ['usage'] }) }
  const upload = useMutation({ mutationFn: async (files: File[]) => { for (const f of files) { const fd = new FormData(); fd.append('file', f); await api.post('/files/', fd) } }, onSuccess: () => { toast.success('Uploaded'); inval() }, onError: (e) => { toast.error(apiError(e).message); inval() } })
  const renM = useMutation({ mutationFn: () => api.patch(`/files/${ren!.id}/`, { name: name.trim() }), onSuccess: () => { setRen(null); inval() }, onError: (e) => toast.error(apiError(e).message) })
  const delM = useMutation({ mutationFn: (f: UserFile) => api.delete(`/files/${f.id}/`), onSuccess: () => { setDel(null); inval(); toast.success('Deleted') } })
  const cols: Column<UserFile>[] = [
    { key: 'n', header: 'Name', render: (f) => <span className="flex items-center gap-2 font-medium"><FileText size={16} className="shrink-0 text-muted" /><span className="truncate">{f.name}</span></span> },
    { key: 'k', header: 'Type', className: 'hidden sm:table-cell', render: (f) => <Badge>{f.kind}</Badge> },
    { key: 's', header: 'Size', className: 'num hidden sm:table-cell text-muted', render: (f) => fmtBytes(f.size_bytes) },
    { key: 'd', header: 'Added', className: 'hidden md:table-cell text-muted', render: (f) => fmtAgo(f.created_at) },
    { key: 'a', header: '', className: 'w-28', render: (f) => <div className="flex justify-end gap-0.5">
      <a href={f.url} aria-label={`Download ${f.name}`} className="rounded-md p-1.5 text-muted hover:bg-card2 hover:text-fg"><Download size={16} /></a>
      <button aria-label={`Rename ${f.name}`} onClick={() => { setRen(f); setName(f.name) }} className="rounded-md p-1.5 text-muted hover:bg-card2 hover:text-fg"><Pencil size={16} /></button>
      <button aria-label={`Delete ${f.name}`} onClick={() => setDel(f)} className="rounded-md p-1.5 text-muted hover:bg-danger/10 hover:text-danger"><Trash2 size={16} /></button></div> },
  ]
  return (
    <div className="mx-auto max-w-5xl p-4 sm:p-8">
      <h1 className="text-2xl font-bold">Saved files</h1><p className="mt-1 text-sm text-muted">PDFs, drawings, spreadsheets and 3D models. Uploaded drawings are stored for reference, dimensions are not read automatically.</p>
      <div className="mt-5"><FileUploader accept=".pdf,.dwg,.dxf,.xlsx,.csv,.txt,.glb,.gltf,.obj,.jpg,.jpeg,.png,.webp" multiple maxMB={25} onFiles={(f) => upload.mutate(f)} disabled={upload.isPending} label={upload.isPending ? 'Uploading...' : 'Drop files here or click to browse'} /></div>
      <div className="mt-5 flex flex-wrap items-end gap-3"><div className="min-w-48 flex-1 sm:max-w-xs"><Input label="Search files" value={q} onChange={(e) => { setQ(e.target.value); setPage(1) }} /></div>
        <div className="w-44"><Select label="Type" value={kind} onChange={(e) => { setKind(e.target.value); setPage(1) }} options={[['', 'All types'], ['pdf', 'PDF'], ['drawing', 'Drawings'], ['document', 'Documents'], ['model', '3D models'], ['other', 'Other']].map(([value, label]) => ({ value, label }))} /></div></div>
      <div className="mt-5">{isLoading ? <Skeleton className="h-48" /> : isError ? <ErrorState message="Could not load files." onRetry={refetch} /> : <DataTable columns={cols} rows={data?.results ?? []} empty={<EmptyState icon={<FileText size={22} />} title="No files yet" text="Upload a file above." />} />}
        {data && <Pagination page={page} count={data.count} pageSize={24} onPage={setPage} />}</div>
      <Modal open={!!ren} onClose={() => setRen(null)} title="Rename file" footer={<><Button variant="ghost" onClick={() => setRen(null)}>Cancel</Button><Button loading={renM.isPending} disabled={!name.trim()} onClick={() => renM.mutate()}>Save</Button></>}><Input label="Name" value={name} onChange={(e) => setName(e.target.value)} maxLength={200} /></Modal>
      <ConfirmDialog open={!!del} onClose={() => setDel(null)} title="Delete file" message={`"${del?.name}" will be permanently deleted.`} loading={delM.isPending} onConfirm={() => del && delM.mutate(del)} />
    </div>
  )
}
