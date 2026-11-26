import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Armchair, BedDouble, Boxes, Briefcase, Calculator, ChefHat, Crown, FileSearch, Hammer, Layers, Minus, PencilRuler, Ruler, Scissors, Sparkles, Tv, Upload, Wand2, Landmark, Cuboid, Table2 } from 'lucide-react'
import type { ElementType } from 'react'
import { api } from '../../lib/api'
import { useAuth } from '../../stores/auth'
import { useT } from '../../lib/i18n'
import { fmtAgo, fmtBytes } from '../../lib/format'
import type { Usage } from '../../lib/types'
import { HoverCard, SectionTitle } from '../../components/ui/Card'
import { Progress, Skeleton, EmptyState, Stat } from '../../components/ui/Misc'
import { useProjects, useSummary } from '../../hooks/queries'
import { PanelSection, RightPanel } from '../../layouts/RightPanel'

interface Action { icon: ElementType; title: string; text: string; to: string }
const MAKER: Action[] = [
  { icon: Calculator, title: 'Calculate Sheet', text: 'Panels and area for a cabinet', to: '/app/calculator' },
  { icon: Scissors, title: 'Create Cutting List', text: 'Parts, materials, edge banding', to: '/app/cutting-lists' },
  { icon: Layers, title: 'Optimize MDF', text: 'Sheet layout with kerf and waste', to: '/app/cutting-lists' },
  { icon: Table2, title: 'Estimate Material', text: 'Area, edge banding, sheet count', to: '/app/calculator' },
  { icon: Boxes, title: 'Generate 3D', text: 'Parametric model, GLB/OBJ export', to: '/app/editor' },
  { icon: FileSearch, title: 'Analyze Drawing', text: 'Upload and attach (manual dimensions)', to: '/app/files' },
  { icon: PencilRuler, title: 'Read Hand Sketch', text: 'Store sketches (manual dimensions)', to: '/app/gallery?source=sketch' },
  { icon: Cuboid, title: 'Cabinet Design', text: 'Start from a base cabinet', to: '/app/editor?template=base-cabinet' },
  { icon: ChefHat, title: 'Kitchen Design', text: 'Kitchen unit templates', to: '/app/editor?category=kitchen' },
  { icon: Armchair, title: 'Wardrobe Design', text: 'Hinged wardrobe presets', to: '/app/editor?template=wardrobe-2door' },
  { icon: Tv, title: 'TV Unit', text: 'Low media console', to: '/app/editor?template=tv-unit' },
  { icon: Briefcase, title: 'Office Furniture', text: 'Filing and storage units', to: '/app/editor?template=office-cabinet' },
]
const OWNER: Action[] = [
  { icon: ChefHat, title: 'Design My Kitchen', text: 'Layout, style and colors', to: '/app/rooms/new?goal=kitchen' },
  { icon: BedDouble, title: 'Design My Bedroom', text: 'Wardrobe, bed and storage', to: '/app/rooms/new?goal=bedroom' },
  { icon: Armchair, title: 'Design My Living Room', text: 'Seating, TV unit, shelves', to: '/app/rooms/new?goal=living' },
  { icon: Sparkles, title: 'Modern Style', text: 'Clean lines, neutral palette', to: '/app/rooms/new' },
  { icon: Landmark, title: 'Classic Style', text: 'Warm wood, traditional detail', to: '/app/rooms/new' },
  { icon: Minus, title: 'Minimal Style', text: 'Light, simple, uncluttered', to: '/app/rooms/new' },
  { icon: Crown, title: 'Luxury Style', text: 'Rich finishes and contrast', to: '/app/rooms/new' },
  { icon: Upload, title: 'Upload My Room', text: 'Keep room photos with your design', to: '/app/gallery?source=room' },
  { icon: Wand2, title: 'Generate Furniture', text: 'Parametric furniture in 3D', to: '/app/editor' },
]

export default function Home() {
  const t = useT(); const user = useAuth((s) => s.user)!; const nav = useNavigate(); const maker = user.role !== 'homeowner'
  const summary = useSummary(); const recent = useProjects({ page_size: 6 })
  const usage = useQuery({ queryKey: ['usage'], queryFn: async () => (await api.get<Usage>('/subscriptions/me/')).data })
  const actions = maker ? MAKER : OWNER
  return (
    <div className="mx-auto max-w-6xl p-4 sm:p-8">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <p className="text-sm text-muted">{t('home.welcome')}, {user.first_name}</p>
        <h1 className="mt-1 text-3xl font-bold sm:text-4xl">{maker ? 'Furniture workshop' : t('home.dream')}</h1>
        <p className="mt-2 max-w-xl text-muted">{maker ? 'Calculate panels, build cutting lists and optimize sheets. Everything is saved to your projects.' : 'Plan your space, choose a style and generate furniture sized for your room.'}</p>
      </motion.div>
      <section className="mt-8"><SectionTitle title={t('home.quick')} />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {actions.map((a, i) => (
            <motion.div key={a.title} className="h-full" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.025 }}>
              <HoverCard as="button" onClick={() => nav(a.to)} className="flex h-full w-full items-start gap-3 p-4">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/15 text-primary"><a.icon size={20} /></span>
                <span><span className="block text-sm font-semibold">{a.title}</span><span className="mt-0.5 block text-xs text-muted">{a.text}</span></span></HoverCard></motion.div>))}
        </div>
      </section>
      <section className="mt-10"><SectionTitle title={t('home.recent')} action={<Link to="/app/projects" className="text-sm text-primary hover:underline">View all</Link>} />
        {recent.isLoading ? <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-24" />)}</div>
          : recent.data?.results.length ? <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {recent.data.results.map((p) => <HoverCard key={p.id} as="button" onClick={() => nav(`/app/projects/${p.id}`)} className="p-4"><p className="font-medium">{p.name}</p>
              <p className="mt-1 text-xs capitalize text-muted">{p.category.replace('_', ' ')} · updated {fmtAgo(p.updated_at)}</p></HoverCard>)}</div>
            : <EmptyState icon={<Hammer size={22} />} title="No projects yet" text="Create a project from the sidebar or start with a quick action above." />}
      </section>
      <RightPanel>
        <PanelSection title="Workspace">
          {summary.data ? <div className="grid grid-cols-2 gap-2">
            <Stat label="Projects" value={summary.data.projects} /><Stat label="Cutting lists" value={summary.data.cutting_lists} />
            <Stat label="Calculations" value={summary.data.calculations} /><Stat label="Images" value={summary.data.images} /></div> : <Skeleton className="h-40" />}
        </PanelSection>
        <PanelSection title="Plan usage">
          {usage.data ? <div className="space-y-4 text-sm">
            <p className="font-medium">{usage.data.plan.name} plan</p>
            <div><div className="mb-1 flex justify-between text-xs text-muted"><span>Projects</span><span className="num">{usage.data.projects.used} / {usage.data.projects.limit ?? 'unlimited'}</span></div>
              <Progress value={usage.data.projects.limit ? (100 * usage.data.projects.used) / usage.data.projects.limit : 0} label="Project usage" /></div>
            <div><div className="mb-1 flex justify-between text-xs text-muted"><span>Storage</span><span className="num">{fmtBytes(usage.data.storage.used_bytes)} / {fmtBytes(usage.data.storage.limit_bytes)}</span></div>
              <Progress value={usage.data.storage.percent} label="Storage usage" /></div>
            <Link to="/app/settings?tab=subscription" className="text-xs text-primary hover:underline">Manage subscription</Link></div> : <Skeleton className="h-28" />}
        </PanelSection>
        <PanelSection title="Tip"><p className="flex gap-2 text-xs text-muted"><Ruler size={16} className="shrink-0 text-primary" />All dimensions are in millimetres. Output is for professional review and is not verified for manufacture.</p></PanelSection>
      </RightPanel>
    </div>
  )
}
