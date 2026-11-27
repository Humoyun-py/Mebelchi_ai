import { useEffect, useRef, useState, type ElementType, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { ArrowRight, Boxes, Calculator, Check, ChevronDown, Cpu, FileSpreadsheet, Layers, Menu, PencilRuler, Scissors, Smartphone, Sofa, X } from 'lucide-react'
import clsx from 'clsx'
import { api } from '../../lib/api'
import { useL, useT } from '../../lib/i18n'
import type { Meta, Plan } from '../../lib/types'
import { useAuth } from '../../stores/auth'
import { Logo } from '../../components/Logo'
import { Button } from '../../components/ui/Button'
import { LanguageMenu } from '../../components/LanguageMenu'
import { Skeleton } from '../../components/ui/Misc'
import { CabinetViewer } from '../../components/three/LazyViewer'
import { useGeometry, useMeta } from '../../hooks/queries'
import { ThemeToggle } from '../../layouts/AppShell'

const Reveal = ({ children, delay = 0, className }: { children: ReactNode; delay?: number; className?: string }) => (
  <motion.div className={className} initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: '-60px' }} transition={{ duration: 0.5, delay }}>{children}</motion.div>
)

function Nav() {
  const t = useT(); const { user } = useAuth(); const [open, setOpen] = useState(false)
  const links = [['#home', t('nav.home')], ['#features', t('nav.features')], ['#how', t('nav.how')], ['#pricing', t('nav.pricing')], ['#about', t('nav.about')]]
  return (
    <header className="glass sticky top-0 z-40 border-b border-line">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
        <Logo />
        <nav className="hidden items-center gap-1 md:flex" aria-label="Primary">
          {links.map(([h, l]) => <a key={h} href={h} className="rounded-lg px-3 py-2 text-sm text-muted transition-colors hover:text-fg">{l}</a>)}
          <Link to="/android" className="rounded-lg px-3 py-2 text-sm text-muted transition-colors hover:text-fg">{t('dl.nav')}</Link>
        </nav>
        <div className="flex items-center gap-1.5">
          <LanguageMenu />
          <ThemeToggle />
          <div className="hidden items-center gap-2 sm:flex">
            {user ? <Link to="/app"><Button size="sm">{t('cta.open')}</Button></Link> : <>
              <Link to="/login"><Button size="sm" variant="ghost">{t('nav.login')}</Button></Link><Link to="/register"><Button size="sm">{t('nav.start')}</Button></Link></>}
          </div>
          <button className="rounded-lg p-2 text-muted hover:bg-card2 md:hidden" onClick={() => setOpen(!open)} aria-label="Toggle menu" aria-expanded={open}>{open ? <X size={20} /> : <Menu size={20} />}</button>
        </div>
      </div>
      {open && <div className="border-t border-line px-4 pb-4 md:hidden">
        {links.map(([h, l]) => <a key={h} href={h} onClick={() => setOpen(false)} className="block rounded-lg px-3 py-3 text-sm text-muted hover:bg-card2 hover:text-fg">{l}</a>)}
        <Link to="/android" onClick={() => setOpen(false)} className="block rounded-lg px-3 py-3 text-sm text-muted hover:bg-card2 hover:text-fg">{t('dl.nav')}</Link>
        <div className="mt-2 flex gap-2">{user ? <Link to="/app" className="flex-1"><Button className="w-full">{t('cta.open')}</Button></Link> : <>
          <Link to="/login" className="flex-1"><Button variant="secondary" className="w-full">{t('nav.login')}</Button></Link><Link to="/register" className="flex-1"><Button className="w-full">{t('nav.start')}</Button></Link></>}</div></div>}
    </header>
  )
}

const HERO = { width: 1200, height: 2200, depth: 600, thickness: 18, shelves: 4, doors: 3, drawers: 0 }

function Hero() {
  const t = useT(); const { data } = useGeometry(HERO)
  const { user } = useAuth()
  return (
    <section id="home" className="relative overflow-hidden">
      <div className="bg-grid absolute inset-0" aria-hidden />
      <div className="absolute -top-40 left-1/2 h-[520px] w-[820px] -translate-x-1/2 rounded-full bg-primary/25 blur-[120px]" aria-hidden />
      <div className="relative mx-auto grid max-w-7xl items-center gap-10 px-4 pb-16 pt-14 sm:px-6 lg:grid-cols-[1.05fr_1fr] lg:pb-24 lg:pt-24">
        <div>
          <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="inline-flex items-center gap-2 rounded-full border border-line bg-card/70 px-3 py-1 text-xs text-muted">
            <Cpu size={13} className="text-primary" />{t('hero.badge')}</motion.span>
          <motion.h1 initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }} className="mt-5 text-5xl font-bold leading-[1.05] sm:text-6xl lg:text-7xl">{t('hero.title')}</motion.h1>
          <motion.p initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12 }} className="mt-5 max-w-xl text-lg text-muted">{t('hero.sub')}</motion.p>
          <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="mt-8 flex flex-wrap gap-3">
            <Link to={user ? '/app' : '/register'}><Button size="lg" icon={<ArrowRight size={18} />}>{t('hero.cta1')}</Button></Link>
            <a href="#features"><Button size="lg" variant="secondary">{t('hero.cta2')}</Button></a>
            <Link to="/android"><Button size="lg" variant="ghost" icon={<Smartphone size={18} />}>{t('dl.nav')}</Button></Link>
          </motion.div>
        </div>
        <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.15, duration: 0.6 }} className="relative">
          {data ? <CabinetViewer boxes={data.boxes} dims={data.dimensions} autoRotate showDims className="h-[380px] sm:h-[480px]" />
            : <Skeleton className="h-[380px] sm:h-[480px]" />}
          {data && <>
            <motion.div animate={{ y: [0, -6, 0] }} transition={{ repeat: Infinity, duration: 5 }} className="glass absolute -left-2 top-8 hidden rounded-xl border border-line p-3 sm:block">
              <p className="text-[11px] text-muted">Overall size</p><p className="num text-sm font-semibold">{data.dimensions.width} x {data.dimensions.height} x {data.dimensions.depth} mm</p></motion.div>
            <motion.div animate={{ y: [0, 6, 0] }} transition={{ repeat: Infinity, duration: 6 }} className="glass absolute -right-2 bottom-10 hidden rounded-xl border border-line p-3 sm:block">
              <p className="text-[11px] text-muted">Parametric parts</p><p className="num text-sm font-semibold">{data.boxes.length} solids</p></motion.div></>}
        </motion.div>
      </div>
    </section>
  )
}

const ICONS: Record<string, ElementType> = { cpu: Cpu, scissors: Scissors, calculator: Calculator, layers: Layers, boxes: Boxes, sofa: Sofa, ruler: PencilRuler, sheet: FileSpreadsheet }

function Stats() {
  const t = useT(); const L = useL(); const { data } = useMeta()
  return (
    <section className="border-y border-line bg-sidebar/60">
      <div className="mx-auto grid max-w-7xl grid-cols-2 gap-6 px-4 py-10 sm:px-6 lg:grid-cols-4">
        {data ? data.stats.map((st, i) => <Reveal key={st.key} delay={i * 0.06}><p className="num text-4xl font-bold">{st.value}</p><p className="mt-1 text-sm font-medium">{L(st.label)}</p><p className="mt-0.5 text-xs text-muted">{L(st.hint)}</p></Reveal>)
          : [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-20" />)}
      </div>
      <p className="pb-4 text-center text-[11px] text-muted">{t('stats.note')}</p>
    </section>
  )
}

function Features() {
  const t = useT(); const L = useL(); const { data } = useMeta()
  return (
    <section id="features" className="mx-auto max-w-7xl scroll-mt-20 px-4 py-20 sm:px-6">
      <Reveal className="mx-auto max-w-2xl text-center"><h2 className="text-3xl font-bold sm:text-4xl">{t('sec.features')}</h2><p className="mt-3 text-muted">{t('sec.featuresSub')}</p></Reveal>
      <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data ? data.content.features.map((f, i) => { const Icon = ICONS[f.icon] ?? Cpu; return (
          <Reveal key={f.icon + i} delay={(i % 3) * 0.07}><motion.div whileHover={{ y: -4 }} className="h-full rounded-2xl border border-line bg-card p-6 transition-colors hover:border-primary/50">
            <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-primary/15 text-primary"><Icon size={22} /></div>
            <h3 className="text-lg font-semibold">{L(f.title)}</h3><p className="mt-2 text-sm leading-relaxed text-muted">{L(f.text)}</p></motion.div></Reveal>) })
          : [0, 1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-44" />)}
      </div>
    </section>
  )
}

function How() {
  const t = useT(); const L = useL(); const { data } = useMeta()
  return (
    <section id="how" className="scroll-mt-20 border-y border-line bg-sidebar/60 py-20">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <Reveal className="mx-auto max-w-2xl text-center"><h2 className="text-3xl font-bold sm:text-4xl">{t('sec.how')}</h2></Reveal>
        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {data ? data.content.steps.map((st, i) => { const Icon = ICONS[st.icon] ?? Boxes; return (
            <Reveal key={i} delay={i * 0.1}><div className="relative rounded-2xl border border-line bg-card p-6">
              <span className="num absolute right-5 top-4 text-5xl font-bold text-line">{i + 1}</span><Icon size={24} className="text-primary" /><h3 className="mt-4 text-lg font-semibold">{L(st.title)}</h3><p className="mt-2 text-sm text-muted">{L(st.text)}</p></div></Reveal>) })
            : [0, 1, 2].map((i) => <Skeleton key={i} className="h-40" />)}
        </div>
      </div>
    </section>
  )
}

function ShowcaseCard({ item }: { item: Meta['showcase'][number] }) {
  const L = useL(); const ref = useRef<HTMLDivElement>(null); const [seen, setSeen] = useState(false)
  useEffect(() => { const el = ref.current; if (!el) return; const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setSeen(true); io.disconnect() } }, { rootMargin: '200px' }); io.observe(el); return () => io.disconnect() }, [])
  const { data } = useGeometry(item.input, item.color, seen)
  return (
    <div ref={ref} className="overflow-hidden rounded-2xl border border-line bg-card">
      {data ? <CabinetViewer boxes={data.boxes} dims={data.dimensions} showDims={false} className="h-64 !rounded-none !border-0" /> : <Skeleton className="h-64 !rounded-none" />}
      <div className="flex items-center justify-between p-4"><h3 className="font-semibold">{L(item.name)}</h3><span className="num text-xs text-muted">{item.input.width} x {item.input.height} x {item.input.depth}</span></div>
    </div>
  )
}
function Showcase() {
  const t = useT(); const { data } = useMeta()
  return (
    <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6">
      <Reveal className="mx-auto max-w-2xl text-center"><h2 className="text-3xl font-bold sm:text-4xl">{t('sec.showcase')}</h2><p className="mt-3 text-muted">{t('sec.showcaseSub')}</p></Reveal>
      <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{data?.showcase.map((s, i) => <ShowcaseCard key={i} item={s} />)}</div>
    </section>
  )
}

function Pricing() {
  const t = useT()
  const { data, isError, isLoading } = useQuery({ queryKey: ['plans'], queryFn: async () => (await api.get<Plan[]>('/subscriptions/plans/')).data, staleTime: 300000 })
  return (
    <section id="pricing" className="scroll-mt-20 border-y border-line bg-sidebar/60 py-20">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <Reveal className="mx-auto max-w-2xl text-center"><h2 className="text-3xl font-bold sm:text-4xl">{t('sec.pricing')}</h2><p className="mt-3 text-muted">{t('sec.pricingSub')}</p></Reveal>
        {isError && <p role="alert" className="mt-10 text-center text-sm text-muted">Plans are unavailable right now. Please try again shortly.</p>}
        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {isLoading && [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-80" />)}
          {data?.map((p, i) => (
            <Reveal key={p.slug} delay={i * 0.06}><div className={clsx('flex h-full flex-col rounded-2xl border bg-card p-6', p.slug === 'professional' ? 'border-primary shadow-[0_0_40px_-12px_var(--primary)]' : 'border-line')}>
              <h3 className="text-lg font-semibold">{p.name}</h3>
              <p className="mt-3"><span className="num text-4xl font-bold">${Number(p.price_usd).toFixed(0)}</span><span className="text-sm text-muted"> / month</span></p>
              <p className="num mt-2 text-xs text-muted">{p.storage_mb >= 1024 ? `${p.storage_mb / 1024} GB` : `${p.storage_mb} MB`} storage · {p.max_projects || 'Unlimited'} projects</p>
              <ul className="mt-5 flex-1 space-y-2.5">{p.features.map((f) => <li key={f} className="flex items-start gap-2 text-sm"><Check size={16} className="mt-0.5 shrink-0 text-success" />{f}</li>)}</ul>
              <Link to="/register" className="mt-6"><Button className="w-full" variant={p.slug === 'professional' ? 'primary' : 'secondary'}>{p.price_usd === '0.00' || Number(p.price_usd) === 0 ? 'Start free' : 'Choose ' + p.name}</Button></Link></div></Reveal>))}
        </div>
      </div>
    </section>
  )
}

function FAQSection() {
  const t = useT(); const L = useL(); const { data } = useMeta(); const [open, setOpen] = useState<number | null>(0)
  return (
    <section className="mx-auto max-w-3xl px-4 py-20 sm:px-6">
      <Reveal><h2 className="text-center text-3xl font-bold sm:text-4xl">{t('sec.faq')}</h2></Reveal>
      <div className="mt-10 divide-y divide-line rounded-2xl border border-line bg-card">
        {data ? data.content.faq.map((f, i) => (
          <div key={i}><button onClick={() => setOpen(open === i ? null : i)} aria-expanded={open === i} className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left font-medium">{L(f.q)}<ChevronDown size={18} className={clsx('shrink-0 text-muted transition-transform', open === i && 'rotate-180')} /></button>
            <motion.div initial={false} animate={{ height: open === i ? 'auto' : 0, opacity: open === i ? 1 : 0 }} className="overflow-hidden"><p className="px-5 pb-5 text-sm leading-relaxed text-muted">{L(f.a)}</p></motion.div></div>))
          : <Skeleton className="h-48" />}
      </div>
    </section>
  )
}

function About() {
  const t = useT()
  return (
    <section id="about" className="scroll-mt-20 border-t border-line bg-sidebar/60 py-20">
      <div className="mx-auto max-w-3xl px-4 text-center sm:px-6"><Reveal><h2 className="text-3xl font-bold sm:text-4xl">{t('sec.about')}</h2>
        <p className="mt-4 leading-relaxed text-muted">{t('sec.aboutText')}</p>
        <Link to="/register" className="mt-8 inline-block"><Button size="lg">{t('cta.account')}</Button></Link></Reveal></div>
    </section>
  )
}

function Footer() {
  const contact = import.meta.env.VITE_CONTACT_EMAIL as string | undefined
  const cols: [string, [string, string][]][] = [['Product', [['Features', '#features'], ['Pricing', '#pricing'], ['How it works', '#how'], ['Android app', '/android']]], ['Resources', [['Documentation', '/api/v1/docs/'], ...(contact ? [['Contact', `mailto:${contact}`] as [string, string]] : [])]], ['Legal', [['Privacy Policy', '/privacy'], ['Terms of Service', '/terms']]]]
  return (
    <footer className="border-t border-line">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-12 sm:px-6 md:grid-cols-[1.4fr_repeat(3,1fr)]">
        <div><Logo /><p className="mt-3 max-w-xs text-sm text-muted">From Idea to Furniture. Design smarter, calculate faster, build better.</p></div>
        {cols.map(([h, ls]) => <div key={h}><h3 className="text-sm font-semibold">{h}</h3><ul className="mt-3 space-y-2">{ls.map(([l, href]) => <li key={l}><a href={href} className="text-sm text-muted hover:text-fg">{l}</a></li>)}</ul></div>)}
      </div>
      <p className="border-t border-line py-5 text-center text-xs text-muted">© {new Date().getFullYear()} MEBELCHI AI. Calculated output is for professional review and is not verified for manufacture.</p>
    </footer>
  )
}

export default function Landing() {
  return <div className="min-h-dvh"><Nav /><Hero /><Stats /><Features /><How /><Showcase /><Pricing /><FAQSection /><About /><Footer /></div>
}
