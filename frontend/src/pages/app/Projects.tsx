import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Archive, ArchiveRestore, Copy, FolderOpen, MoreHorizontal, Pencil, Pin, PinOff, Plus, Trash2 } from 'lucide-react'
import { api, apiError } from '../../lib/api'
import { fmtAgo } from '../../lib/format'
import type { Project } from '../../lib/types'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Field'
import { ConfirmDialog, Modal } from '../../components/ui/Modal'
import { Dropdown } from '../../components/ui/Dropdown'
import { Tabs } from '../../components/ui/Tabs'
import { Badge, type Column, DataTable, EmptyState, ErrorState, Pagination, Skeleton } from '../../components/ui/Misc'
import { toast } from '../../components/ui/Toast'
import { useDebounced, useProjects } from '../../hooks/queries'
import { NewProjectModal } from '../../layouts/AppShell'

export function useProjectActions() {
  const qc = useQueryClient()
  const done = (msg: string) => () => { qc.invalidateQueries({ queryKey: ['projects'] }); qc.invalidateQueries({ queryKey: ['summary'] }); toast.success(msg) }
  const fail = (e: unknown) => toast.error(apiError(e).message)
  return {
    pin: useMutation({ mutationFn: (id: number) => api.post(`/projects/${id}/pin/`), onSuccess: done('Updated'), onError: fail }),
    archive: useMutation({ mutationFn: (id: number) => api.post(`/projects/${id}/archive/`), onSuccess: done('Project archived'), onError: fail }),
    unarchive: useMutation({ mutationFn: (id: number) => api.post(`/projects/${id}/unarchive/`), onSuccess: done('Project restored'), onError: fail }),
    duplicate: useMutation({ mutationFn: (id: number) => api.post(`/projects/${id}/duplicate/`), onSuccess: done('Project duplicated'), onError: fail }),
    remove: useMutation({ mutationFn: (id: number) => api.delete(`/projects/${id}/`), onSuccess: done('Project deleted'), onError: fail }),
    rename: useMutation({ mutationFn: ({ id, name }: { id: number; name: string }) => api.patch(`/projects/${id}/`, { name }), onSuccess: done('Renamed'), onError: fail }),
  }
}

export default function Projects() {
  const nav = useNavigate(); const [params] = useSearchParams()
  const [tab, setTab] = useState<'active' | 'archived'>('active'); const [q, setQ] = useState(''); const [page, setPage] = useState(1)
  const [newOpen, setNewOpen] = useState(false); const [del, setDel] = useState<Project | null>(null); const [ren, setRen] = useState<Project | null>(null); const [name, setName] = useState('')
  const dq = useDebounced(q, 300); const folder = params.get('folder')
  const { data, isLoading, isError, refetch } = useProjects({ status: tab, search: dq, page, ...(folder ? { folder } : {}) })
  const a = useProjectActions()
  const cols: Column<Project>[] = [
    { key: 'n', header: 'Name', render: (p) => <button onClick={() => nav(`/app/projects/${p.id}`)} className="flex items-center gap-2 text-left font-medium hover:text-primary">{p.pinned && <Pin size={14} className="text-primary" />}{p.name}</button> },
    { key: 'c', header: 'Category', className: 'hidden sm:table-cell', render: (p) => <Badge>{p.category.replace('_', ' ')}</Badge> },
    { key: 'd', header: 'Size (mm)', className: 'hidden md:table-cell num text-muted', render: (p) => p.width ? `${p.width} x ${p.height ?? '-'} x ${p.depth ?? '-'}` : '-' },
    { key: 'u', header: 'Updated', className: 'hidden sm:table-cell text-muted', render: (p) => fmtAgo(p.updated_at) },
    { key: 'a', header: '', className: 'w-10', render: (p) => <Dropdown trigger={<button aria-label={`Actions for ${p.name}`} className="rounded-md p-1.5 text-muted hover:bg-card2 hover:text-fg"><MoreHorizontal size={18} /></button>} items={[
      { label: 'Open', icon: <FolderOpen size={16} />, onClick: () => nav(`/app/projects/${p.id}`) },
      { label: 'Rename', icon: <Pencil size={16} />, onClick: () => { setRen(p); setName(p.name) } },
      { label: p.pinned ? 'Unpin' : 'Pin', icon: p.pinned ? <PinOff size={16} /> : <Pin size={16} />, onClick: () => a.pin.mutate(p.id) },
      { label: 'Duplicate', icon: <Copy size={16} />, onClick: () => a.duplicate.mutate(p.id) },
      p.status === 'active' ? { label: 'Archive', icon: <Archive size={16} />, onClick: () => a.archive.mutate(p.id) } : { label: 'Restore', icon: <ArchiveRestore size={16} />, onClick: () => a.unarchive.mutate(p.id) },
      { label: 'Delete', icon: <Trash2 size={16} />, danger: true, onClick: () => setDel(p) }]} /> },
  ]
  return (
    <div className="mx-auto max-w-5xl p-4 sm:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="text-2xl font-bold">Projects</h1><Button icon={<Plus size={16} />} onClick={() => setNewOpen(true)}>New project</Button></div>
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Tabs tabs={[{ id: 'active', label: 'Active' }, { id: 'archived', label: 'Archived' }]} value={tab} onChange={(v) => { setTab(v); setPage(1) }} />
        <div className="min-w-48 flex-1 sm:max-w-xs"><Input label="Search projects" value={q} onChange={(e) => { setQ(e.target.value); setPage(1) }} /></div>
      </div>
      <div className="mt-5">
        {isLoading ? <Skeleton className="h-64" /> : isError ? <ErrorState message="Could not load projects." onRetry={refetch} />
          : <DataTable columns={cols} rows={data?.results ?? []} onRowClick={(p) => nav(`/app/projects/${p.id}`)} empty={<EmptyState icon={<FolderOpen size={22} />} title={tab === 'active' ? 'No projects found' : 'No archived projects'} text={q ? 'Try a different search.' : 'Projects you create will appear here.'} action={tab === 'active' && !q ? <Button onClick={() => setNewOpen(true)}>New project</Button> : undefined} />} />}
        {data && <Pagination page={page} count={data.count} pageSize={24} onPage={setPage} />}
      </div>
      <NewProjectModal open={newOpen} onClose={() => setNewOpen(false)} />
      <ConfirmDialog open={!!del} onClose={() => setDel(null)} title="Delete project" message={`"${del?.name}" and all its calculations, cutting lists and designs will be permanently deleted.`} loading={a.remove.isPending}
        onConfirm={() => del && a.remove.mutate(del.id, { onSuccess: () => setDel(null) })} />
      <Modal open={!!ren} onClose={() => setRen(null)} title="Rename project" footer={<><Button variant="ghost" onClick={() => setRen(null)}>Cancel</Button><Button disabled={!name.trim()} loading={a.rename.isPending} onClick={() => ren && a.rename.mutate({ id: ren.id, name: name.trim() }, { onSuccess: () => setRen(null) })}>Save</Button></>}>
        <Input label="Project name" value={name} onChange={(e) => setName(e.target.value)} maxLength={160} /></Modal>
    </div>
  )
}
