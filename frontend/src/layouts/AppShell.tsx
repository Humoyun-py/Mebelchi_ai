import { useEffect, useState, type ReactNode } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { Bell, Box, Calculator, ChevronsLeft, ChevronsRight, FileText, FolderClosed, FolderPlus, Image as ImageIcon, LayoutDashboard, LogOut, Menu, MessageSquare,
  Armchair, Building2, Moon, PanelRight, Pin, Plus, Ruler, Scissors, Search, Settings, ShieldCheck, Sun, Layers, User as UserIcon, X } from 'lucide-react'
import clsx from 'clsx'
import { api, apiError } from '../lib/api'
import { useL, useT } from '../lib/i18n'
import { fmtAgo } from '../lib/format'
import type { Folder, Notification, Page, Project } from '../lib/types'
import { useAuth } from '../stores/auth'
import { useUI } from '../stores/ui'
import { Logo } from '../components/Logo'
import { LanguageMenu } from '../components/LanguageMenu'
import { Button } from '../components/ui/Button'
import { Input, Select } from '../components/ui/Field'
import { Modal } from '../components/ui/Modal'
import { Dropdown } from '../components/ui/Dropdown'
import { Tooltip } from '../components/ui/Tooltip'
import { toast } from '../components/ui/Toast'
import { useProjects, useDebounced, useMeta } from '../hooks/queries'


export function NewProjectModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const nav = useNavigate(); const qc = useQueryClient(); const L = useL(); const meta = useMeta()
  const [name, setName] = useState(''); const [category, setCategory] = useState('cabinet'); const [err, setErr] = useState('')
  const m = useMutation({
    mutationFn: async () => (await api.post<Project>('/projects/', { name: name.trim(), category })).data,
    onSuccess: (p) => { qc.invalidateQueries({ queryKey: ['projects'] }); qc.invalidateQueries({ queryKey: ['summary'] }); toast.success('Project created'); setName(''); onClose(); nav(`/app/projects/${p.id}`) },
    onError: (e) => setErr(apiError(e).message),
  })
  return (
    <Modal open={open} onClose={onClose} title="New project"
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button loading={m.isPending} disabled={!name.trim()} onClick={() => { setErr(''); m.mutate() }}>Create project</Button></>}>
      <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); if (name.trim()) m.mutate() }}>
        <Input label="Project name" value={name} onChange={(e) => setName(e.target.value)} maxLength={160} error={err} />
        <Select label="Category" value={category} onChange={(e) => setCategory(e.target.value)} options={(meta.data?.project_categories ?? []).map((c) => ({ value: c.value, label: L(c.label) }))} />
      </form>
    </Modal>
  )
}

function SearchModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [q, setQ] = useState(''); const dq = useDebounced(q, 250); const nav = useNavigate()
  const { data, isFetching } = useProjects({ search: dq, page_size: 8 })
  return (
    <Modal open={open} onClose={onClose} title="Search projects">
      <Input label="Search by name or description" value={q} onChange={(e) => setQ(e.target.value)} />
      <ul className="mt-3 max-h-72 space-y-1 overflow-y-auto">
        {data?.results.map((p) => (
          <li key={p.id}><button onClick={() => { onClose(); nav(`/app/projects/${p.id}`) }} className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm hover:bg-card2">
            <span>{p.name}</span><span className="text-xs text-muted">{p.category}</span></button></li>))}
        {!isFetching && data && !data.results.length && <li className="px-3 py-6 text-center text-sm text-muted">No projects match.</li>}
      </ul>
    </Modal>
  )
}

function NavItem({ to, icon, label, collapsed, end }: { to: string; icon: ReactNode; label: string; collapsed: boolean; end?: boolean }) {
  const link = (
    <NavLink to={to} end={end} className={({ isActive }) => clsx('flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors', collapsed && 'justify-center px-0',
      isActive ? 'bg-primary/15 text-fg ring-1 ring-primary/30' : 'text-muted hover:bg-card2 hover:text-fg')}>
      <span className="shrink-0">{icon}</span>{!collapsed && <span className="truncate">{label}</span>}
    </NavLink>
  )
  return collapsed ? <Tooltip label={label}>{link}</Tooltip> : link
}

function SidebarBody({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  const t = useT(); const user = useAuth((s) => s.user)!; const nav = useNavigate(); const qc = useQueryClient()
  const [newOpen, setNewOpen] = useState(false); const [searchOpen, setSearchOpen] = useState(false); const [folderOpen, setFolderOpen] = useState(false); const [folderName, setFolderName] = useState('')
  const pinned = useProjects({ pinned: true, page_size: 5 }); const recent = useProjects({ ordering: '-updated_at', page_size: 6 })
  const folders = useQuery({ queryKey: ['folders'], queryFn: async () => (await api.get<Folder[]>('/folders/')).data })
  const addFolder = useMutation({ mutationFn: async () => api.post('/folders/', { name: folderName.trim() }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['folders'] }); setFolderOpen(false); setFolderName(''); toast.success('Folder created') }, onError: (e) => toast.error(apiError(e).message) })
  const maker = user.role !== 'homeowner'
  const sec = (s: string) => !collapsed && <p className="mb-1.5 mt-5 px-3 text-[11px] font-semibold uppercase tracking-wider text-muted/80">{s}</p>
  const go = () => onNavigate?.()
  return (
    <div className="flex h-full flex-col" onClick={(e) => (e.target as HTMLElement).closest('a') && go()}>
      <div className={clsx('flex h-14 items-center px-4', collapsed && 'justify-center px-0')}><Logo to="/app" collapsed={collapsed} /></div>
      <div className="px-3">
        {collapsed ? <Tooltip label={t('side.new')}><Button className="w-full !px-0" onClick={() => setNewOpen(true)} aria-label={t('side.new')}><Plus size={18} /></Button></Tooltip>
          : <Button className="w-full" icon={<Plus size={16} />} onClick={() => setNewOpen(true)}>{t('side.new')}</Button>}
        <button onClick={() => setSearchOpen(true)} aria-label={t('side.search')} className={clsx('mt-2 flex w-full items-center gap-3 rounded-lg border border-line px-3 py-2 text-sm text-muted hover:text-fg', collapsed && 'justify-center px-0')}>
          <Search size={16} />{!collapsed && <span>{t('side.search')}</span>}</button>
      </div>
      <nav className="mt-3 min-h-0 flex-1 overflow-y-auto px-3 pb-3" aria-label="Main">
        <NavItem to="/app" end icon={<LayoutDashboard size={18} />} label={t('side.dashboard')} collapsed={collapsed} />
        <NavItem to="/app/assistant" icon={<MessageSquare size={18} />} label={t('side.chat')} collapsed={collapsed} />
        <NavItem to="/app/projects" icon={<Layers size={18} />} label={t('side.projects')} collapsed={collapsed} />
        <NavItem to="/app/workshops" icon={<Building2 size={18} />} label={t('side.workshops')} collapsed={collapsed} />
        {sec(maker ? t('side.workshop') : t('side.design'))}
        {maker ? (<>
          <NavItem to="/app/calculator" icon={<Calculator size={18} />} label={t('side.calc')} collapsed={collapsed} />
          <NavItem to="/app/cutting-lists" icon={<Scissors size={18} />} label={t('side.cuts')} collapsed={collapsed} />
          <NavItem to="/app/editor" icon={<Ruler size={18} />} label={t('side.editor')} collapsed={collapsed} />
        </>) : null}
        <NavItem to="/app/rooms" icon={<Armchair size={18} />} label={t('side.rooms')} collapsed={collapsed} />
        {!collapsed && pinned.data?.results.length ? (<>{sec(t('side.pinned'))}
          {pinned.data.results.map((p) => <NavLink key={p.id} to={`/app/projects/${p.id}`} className="flex items-center gap-2 rounded-md px-3 py-1.5 text-sm text-muted hover:bg-card2 hover:text-fg"><Pin size={14} /><span className="truncate">{p.name}</span></NavLink>)}</>) : null}
        {!collapsed && recent.data?.results.length ? (<>{sec(t('side.recent'))}
          {recent.data.results.map((p) => <NavLink key={p.id} to={`/app/projects/${p.id}`} className="block truncate rounded-md px-3 py-1.5 text-sm text-muted hover:bg-card2 hover:text-fg">{p.name}</NavLink>)}</>) : null}
        {!collapsed && (<>
          <div className="mb-1.5 mt-5 flex items-center justify-between px-3"><p className="text-[11px] font-semibold uppercase tracking-wider text-muted/80">{t('side.folders')}</p>
            <button onClick={() => setFolderOpen(true)} aria-label="New folder" className="text-muted hover:text-fg"><FolderPlus size={14} /></button></div>
          {folders.data?.map((f) => <NavLink key={f.id} to={`/app/projects?folder=${f.id}`} className="flex items-center justify-between rounded-md px-3 py-1.5 text-sm text-muted hover:bg-card2 hover:text-fg">
            <span className="flex items-center gap-2 truncate"><FolderClosed size={14} />{f.name}</span><span className="num text-xs">{f.project_count}</span></NavLink>)}
        </>)}
        {sec(t('side.library'))}
        <NavItem to="/app/gallery" icon={<ImageIcon size={18} />} label={t('side.images')} collapsed={collapsed} />
        <NavItem to="/app/designs" icon={<Box size={18} />} label={t('side.models')} collapsed={collapsed} />
        <NavItem to="/app/files" icon={<FileText size={18} />} label={t('side.files')} collapsed={collapsed} />
      </nav>
      <div className="space-y-1 border-t border-line p-3">
        {user.is_admin && <NavItem to="/app/admin" icon={<ShieldCheck size={18} />} label={t('side.admin')} collapsed={collapsed} />}
        <NavItem to="/app/settings" icon={<Settings size={18} />} label={t('side.settings')} collapsed={collapsed} />
        <NavItem to="/app/settings?tab=profile" icon={<UserIcon size={18} />} label={t('side.profile')} collapsed={collapsed} />
      </div>
      <NewProjectModal open={newOpen} onClose={() => setNewOpen(false)} />
      <SearchModal open={searchOpen} onClose={() => setSearchOpen(false)} />
      <Modal open={folderOpen} onClose={() => setFolderOpen(false)} title="New folder" footer={<><Button variant="ghost" onClick={() => setFolderOpen(false)}>Cancel</Button><Button disabled={!folderName.trim()} loading={addFolder.isPending} onClick={() => addFolder.mutate()}>Create</Button></>}>
        <Input label="Folder name" value={folderName} onChange={(e) => setFolderName(e.target.value)} maxLength={120} onKeyDown={(e) => e.key === 'Enter' && folderName.trim() && addFolder.mutate()} />
      </Modal>
      <span hidden>{String(!!nav)}</span>
    </div>
  )
}

function Notifications() {
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['notifications'], queryFn: async () => (await api.get<Page<Notification>>('/notifications/', { params: { page_size: 8 } })).data, refetchInterval: 60000 })
  const unread = data?.results.filter((n) => !n.read).length ?? 0
  const readAll = useMutation({ mutationFn: () => api.post('/notifications/read-all/'), onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }) })
  return <NotificationsMenu items={data?.results ?? []} unread={unread} onReadAll={() => readAll.mutate()} />
}

function NotificationsMenu({ items, unread, onReadAll }: { items: Notification[]; unread: number; onReadAll: () => void }) {
  const [open, setOpen] = useState(false)
  useEffect(() => { if (!open) return; const k = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false); document.addEventListener('keydown', k); return () => document.removeEventListener('keydown', k) }, [open])
  return (
    <div className="relative">
      <button onClick={() => setOpen(!open)} aria-label={`Notifications${unread ? `, ${unread} unread` : ''}`} aria-expanded={open} className="relative rounded-lg p-2 text-muted hover:bg-card2 hover:text-fg">
        <Bell size={18} />{unread > 0 && <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-primary" />}</button>
      <AnimatePresence>{open && (<>
        <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
        <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="absolute right-0 z-40 mt-2 w-[min(92vw,22rem)] rounded-xl border border-line bg-card shadow-2xl">
          <div className="flex items-center justify-between border-b border-line px-4 py-3"><p className="text-sm font-semibold">Notifications</p>
            {unread > 0 && <button onClick={onReadAll} className="text-xs text-primary hover:underline">Mark all read</button>}</div>
          <ul className="max-h-80 overflow-y-auto">
            {items.map((n) => <li key={n.id} className={clsx('border-b border-line/60 px-4 py-3 last:border-0', !n.read && 'bg-primary/5')}>
              <p className="text-sm font-medium">{n.title}</p>{n.body && <p className="mt-0.5 text-xs text-muted">{n.body}</p>}<p className="mt-1 text-[11px] text-muted">{fmtAgo(n.created_at)}</p></li>)}
            {!items.length && <li className="px-4 py-8 text-center text-sm text-muted">You are all caught up.</li>}
          </ul>
        </motion.div></>)}</AnimatePresence>
    </div>
  )
}

export function ThemeToggle() {
  const { theme, setTheme } = useUI(); const user = useAuth((s) => s.user); const setUser = useAuth((s) => s.setUser)
  const flip = async () => {
    const next = theme === 'dark' ? 'light' : 'dark'; setTheme(next)
    if (user) { try { setUser((await api.patch('/users/me/', { theme: next })).data) } catch { /* local preference still applied */ } }
  }
  return <button onClick={flip} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`} className="rounded-lg p-2 text-muted hover:bg-card2 hover:text-fg">{theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}</button>
}

export default function AppShell() {
  const { sidebarCollapsed, toggleSidebar, rightPanelOpen, toggleRightPanel, mobileNavOpen, setMobileNav } = useUI()
  const user = useAuth((s) => s.user)!; const logout = useAuth((s) => s.logout); const nav = useNavigate(); const loc = useLocation()
  const [overlayPanel, setOverlayPanel] = useState(false)
  const togglePanel = () => (window.matchMedia('(min-width: 1280px)').matches ? toggleRightPanel() : setOverlayPanel((v) => !v))
  useEffect(() => { setMobileNav(false); setOverlayPanel(false) }, [loc.pathname, setMobileNav])
  return (
    <div className="flex h-dvh overflow-hidden bg-bg">
      <motion.aside animate={{ width: sidebarCollapsed ? 72 : 260 }} transition={{ duration: 0.2 }} className="hidden shrink-0 border-r border-line bg-sidebar md:block" aria-label="Sidebar">
        <SidebarBody collapsed={sidebarCollapsed} />
      </motion.aside>
      <AnimatePresence>{mobileNavOpen && (
        <motion.div className="fixed inset-0 z-40 md:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <div className="absolute inset-0 bg-black/60" onClick={() => setMobileNav(false)} />
          <motion.aside initial={{ x: -280 }} animate={{ x: 0 }} exit={{ x: -280 }} transition={{ type: 'tween', duration: 0.2 }} className="absolute inset-y-0 left-0 w-[280px] border-r border-line bg-sidebar" aria-label="Navigation drawer">
            <button onClick={() => setMobileNav(false)} aria-label="Close menu" className="absolute right-3 top-3 z-10 rounded-md p-1.5 text-muted hover:bg-card2"><X size={18} /></button>
            <SidebarBody collapsed={false} onNavigate={() => setMobileNav(false)} />
          </motion.aside></motion.div>)}</AnimatePresence>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-2 border-b border-line px-3 sm:px-4">
          <button onClick={() => setMobileNav(true)} aria-label="Open menu" className="rounded-lg p-2 text-muted hover:bg-card2 md:hidden"><Menu size={20} /></button>
          <button onClick={toggleSidebar} aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'} className="hidden rounded-lg p-2 text-muted hover:bg-card2 hover:text-fg md:block">{sidebarCollapsed ? <ChevronsRight size={18} /> : <ChevronsLeft size={18} />}</button>
          <div className="flex-1" />
          <Notifications />
          <LanguageMenu />
          <ThemeToggle />
          <button onClick={togglePanel} aria-label="Toggle details panel" aria-pressed={rightPanelOpen || overlayPanel} className={clsx('rounded-lg p-2 hover:bg-card2', rightPanelOpen || overlayPanel ? 'text-primary' : 'text-muted')}><PanelRight size={18} /></button>
          <Dropdown trigger={<button aria-label="Account menu" className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-full bg-primary text-xs font-semibold text-on-primary">
            {user.avatar_url ? <img src={user.avatar_url} alt="" className="h-full w-full object-cover" /> : (user.first_name[0] + user.last_name[0]).toUpperCase()}</button>}
            items={[{ label: 'Settings', icon: <Settings size={16} />, onClick: () => nav('/app/settings') }, { label: 'Log out', icon: <LogOut size={16} />, danger: true, onClick: async () => { await logout(); nav('/') } }]} />
        </header>
        <div className="flex min-h-0 flex-1">
          <main className="min-w-0 flex-1 overflow-y-auto" id="main"><motion.div key={loc.pathname} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}><Outlet /></motion.div></main>
          <aside id="right-panel-slot" aria-label="Details panel" className={clsx('shrink-0 overflow-y-auto border-l border-line bg-sidebar empty:hidden',
            overlayPanel ? 'fixed inset-y-0 right-0 z-30 block w-[min(92vw,20rem)] pt-14 shadow-2xl xl:static xl:z-auto xl:w-80 xl:pt-0 xl:shadow-none' : 'hidden',
            rightPanelOpen ? 'xl:block xl:w-80' : 'xl:hidden')} />
        </div>
      </div>
    </div>
  )
}
