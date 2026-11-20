import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, Hammer, Home, Ruler, Sofa } from 'lucide-react'
import { CabinetViewer } from '../../components/three/LazyViewer'
import { Skeleton } from '../../components/ui/Misc'
import { LanguageMenu } from '../../components/LanguageMenu'
import { useGeometry } from '../../hooks/queries'
import { useT } from '../../lib/i18n'
import { ThemeToggle } from '../../layouts/AppShell'
import { api, apiError } from '../../lib/api'
import type { Role, User } from '../../lib/types'
import { useAuth } from '../../stores/auth'
import { Logo } from '../../components/Logo'
import { toast } from '../../components/ui/Toast'

const MAKER_PIECE = { width: 1000, height: 2200, depth: 580, thickness: 18, shelves: 4, doors: 2, drawers: 0 }
const TV_PIECE = { width: 1600, height: 450, depth: 400, thickness: 18, shelves: 1, doors: 2, drawers: 0 }
const SHELF_PIECE = { width: 800, height: 1800, depth: 300, thickness: 18, shelves: 5, doors: 0, drawers: 0 }

/** Live renders from the platform's own geometry engine (no stock images). */
function MakerArt() {
  const { data } = useGeometry(MAKER_PIECE)
  return data ? <CabinetViewer boxes={data.boxes} dims={data.dimensions} autoRotate interactive={false} showDims className="h-full !border-0 !bg-transparent" /> : <Skeleton className="h-full" />
}
function HomeArt() {
  const tv = useGeometry(TV_PIECE, '#e5e7eb'); const shelf = useGeometry(SHELF_PIECE, '#8b6f4e')
  if (!tv.data || !shelf.data) return <Skeleton className="h-full" />
  const gap = 150, dx = tv.data.dimensions.width + gap
  const boxes = [...tv.data.boxes, ...shelf.data.boxes.map((b) => ({ ...b, x: b.x + dx }))]
  return <CabinetViewer boxes={boxes} dims={{ width: dx + shelf.data.dimensions.width, height: shelf.data.dimensions.height, depth: 500 }} autoRotate interactive={false} showDims={false} className="h-full !border-0 !bg-transparent" />
}

export default function RoleSelect() {
  const t = useT(); const user = useAuth((s) => s.user)!; const setUser = useAuth((s) => s.setUser); const nav = useNavigate(); const [busy, setBusy] = useState<Role | null>(null)
  const options: { role: Role; title: string; text: string; points: [React.ElementType, string][]; cta: string; art: React.ReactNode }[] = [
    { role: 'maker', title: t('role.maker'), text: t('role.makerText'), cta: t('role.makerCta'), art: <MakerArt />, points: [[Ruler, t('role.maker1')], [Hammer, t('role.maker2')]] },
    { role: 'homeowner', title: t('role.home'), text: t('role.homeText'), cta: t('role.homeCta'), art: <HomeArt />, points: [[Sofa, t('role.home1')], [Home, t('role.home2')]] },
  ]
  const pick = async (role: Role) => {
    setBusy(role)
    try { setUser((await api.post<User>('/users/me/role/', { role })).data); nav('/app', { replace: true }) }
    catch (e) { toast.error(apiError(e).message); setBusy(null) }
  }
  return (
    <div className="relative min-h-dvh overflow-hidden px-5 py-8">
      <div className="bg-grid absolute inset-0" aria-hidden />
      <div className="absolute left-1/2 top-10 h-72 w-[40rem] -translate-x-1/2 rounded-full bg-primary/20 blur-[120px]" aria-hidden />
      <div className="relative mx-auto max-w-5xl">
        <div className="flex items-center justify-between"><Logo /><div className="flex items-center gap-1"><LanguageMenu /><ThemeToggle /></div></div>
        <div className="mx-auto mt-10 max-w-xl text-center"><h1 className="text-3xl font-bold sm:text-4xl">{t('role.title')}</h1>
          <p className="mt-3 text-muted">{user.first_name}, {t('role.sub')}</p></div>
        <div className="mt-10 grid gap-5 md:grid-cols-2">
          {options.map((o, i) => (
            <motion.button key={o.role} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 * i }} whileHover={{ y: -6 }} onClick={() => pick(o.role)} disabled={!!busy}
              className="group rounded-2xl border border-line bg-card p-5 text-left transition-colors hover:border-primary/60 hover:bg-card2 disabled:opacity-60">
              <div className="mb-5 h-64 overflow-hidden rounded-xl border border-line bg-gradient-to-b from-card2 to-bg" aria-hidden>{o.art}</div>
              <h2 className="text-xl font-semibold">{o.title}</h2><p className="mt-1 text-sm text-muted">{o.text}</p>
              <ul className="mt-4 space-y-2">{o.points.map(([Icon, text]) => <li key={text} className="flex items-center gap-2 text-sm text-muted"><Icon size={16} className="text-primary" />{text}</li>)}</ul>
              <span className="mt-6 flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-primary text-sm font-medium text-on-primary transition-colors group-hover:bg-primary-hover">
                {busy === o.role ? '...' : o.cta}<ArrowRight size={16} /></span>
            </motion.button>))}
        </div>
      </div>
    </div>
  )
}
