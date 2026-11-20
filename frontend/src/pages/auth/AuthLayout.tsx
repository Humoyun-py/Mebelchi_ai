import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Boxes, Calculator, Layers } from 'lucide-react'
import { Logo } from '../../components/Logo'
import { LanguageMenu } from '../../components/LanguageMenu'
import { CabinetViewer } from '../../components/three/LazyViewer'
import { useGeometry } from '../../hooks/queries'
import { useT } from '../../lib/i18n'
import { ThemeToggle } from '../../layouts/AppShell'

const SHOWCASE = { width: 1000, height: 2200, depth: 580, thickness: 18, shelves: 4, doors: 2, drawers: 0 }

export default function AuthLayout({ title, subtitle, children, footer, wide }: { title: string; subtitle: string; children: ReactNode; footer: ReactNode; wide?: boolean }) {
  const t = useT(); const { data } = useGeometry(SHOWCASE)
  const feats = [[Calculator, t('side.f1')], [Layers, t('side.f2')], [Boxes, t('side.f3')]] as const
  return (
    <div className="grid min-h-dvh lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
      <div className="relative flex flex-col overflow-hidden px-5 py-6 sm:px-10">
        <div className="pointer-events-none absolute -left-24 -top-24 h-72 w-72 rounded-full bg-primary/20 blur-[90px]" aria-hidden />
        <div className="relative flex items-center justify-between"><Logo /><div className="flex items-center gap-1"><LanguageMenu /><ThemeToggle /></div></div>
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className={`relative mx-auto flex w-full flex-1 flex-col justify-center py-10 ${wide ? 'max-w-lg' : 'max-w-md'}`}>
          <h1 className="bg-gradient-to-br from-fg via-fg to-primary bg-clip-text text-4xl font-bold text-transparent">{title}</h1>
          <p className="mt-2 text-sm text-muted">{subtitle}</p>
          <div className="mt-8 rounded-2xl border border-line bg-card/60 p-5 shadow-[0_20px_60px_-30px_rgb(37_99_235/0.5)] backdrop-blur sm:p-6">{children}</div>
          <div className="mt-6 text-center text-sm text-muted">{footer}</div>
        </motion.div>
        <p className="relative text-center text-xs text-muted"><Link to="/" className="hover:text-fg">{t('auth.back')}</Link></p>
      </div>
      <div className="relative hidden overflow-hidden border-l border-line bg-sidebar lg:block" aria-hidden>
        <div className="bg-grid absolute inset-0" />
        <motion.div animate={{ opacity: [0.5, 0.9, 0.5] }} transition={{ repeat: Infinity, duration: 7 }} className="absolute left-1/2 top-24 h-80 w-80 -translate-x-1/2 rounded-full bg-primary/30 blur-[110px]" />
        <div className="relative flex h-full flex-col justify-between p-10">
          <div className="relative flex-1">
            {data ? <CabinetViewer boxes={data.boxes} dims={data.dimensions} autoRotate interactive={false} className="h-full min-h-[420px] !border-0 !bg-transparent" /> : <div className="h-full min-h-[420px]" />}
            <motion.div animate={{ y: [0, -7, 0] }} transition={{ repeat: Infinity, duration: 5 }} className="glass absolute left-0 top-8 rounded-xl border border-line px-3 py-2"><p className="text-[11px] text-muted">W x H x D</p><p className="num text-sm font-semibold">1000 x 2200 x 580 mm</p></motion.div>
            <motion.div animate={{ y: [0, 7, 0] }} transition={{ repeat: Infinity, duration: 6 }} className="glass absolute bottom-10 right-0 rounded-xl border border-line px-3 py-2"><p className="text-[11px] text-muted">MDF 18 mm</p><p className="num text-sm font-semibold">{data ? `${data.boxes.length} solids` : '...'}</p></motion.div>
          </div>
          <div>
            <p className="font-display text-3xl font-semibold">{t('side.tag')}</p>
            <ul className="mt-5 space-y-3">{feats.map(([Icon, text], i) => (
              <motion.li key={text} initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 + i * 0.12 }} className="flex items-center gap-3 text-sm text-muted">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/15 text-primary"><Icon size={16} /></span>{text}</motion.li>))}</ul>
          </div>
        </div>
      </div>
    </div>
  )
}
