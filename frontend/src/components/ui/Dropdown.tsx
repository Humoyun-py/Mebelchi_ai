import { useEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion } from 'framer-motion'
import clsx from 'clsx'

export interface MenuItem { label: string; icon?: ReactNode; onClick: () => void; danger?: boolean; disabled?: boolean }

function MenuList({ items, onPick }: { items: MenuItem[]; onPick: () => void }) {
  return (
    <>{items.map((it) => (
      <button key={it.label} role="menuitem" disabled={it.disabled} onClick={() => { onPick(); it.onClick() }}
        className={clsx('flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm disabled:opacity-40', it.danger ? 'text-danger hover:bg-danger/10' : 'text-fg hover:bg-card2')}>
        {it.icon}{it.label}</button>
    ))}</>
  )
}
function useOutside(refs: React.RefObject<HTMLElement | null>[], close: () => void, open: boolean) {
  useEffect(() => {
    if (!open) return
    const h = (e: MouseEvent) => { if (!refs.some((r) => r.current?.contains(e.target as Node))) close() }
    const k = (e: KeyboardEvent) => e.key === 'Escape' && close()
    const sc = (e: Event) => { if (!refs.some((r) => r.current?.contains(e.target as Node))) close() }
    document.addEventListener('mousedown', h); document.addEventListener('keydown', k); window.addEventListener('resize', close); window.addEventListener('scroll', sc, true)
    return () => { document.removeEventListener('mousedown', h); document.removeEventListener('keydown', k); window.removeEventListener('resize', close); window.removeEventListener('scroll', sc, true) }
  }, [open, close, refs])
}

/** Menu is rendered in a portal with fixed positioning, so table/card `overflow` can never clip it. */
export function Dropdown({ trigger, items, align = 'right' }: { trigger: ReactNode; items: MenuItem[]; align?: 'left' | 'right' }) {
  const [open, setOpen] = useState(false); const [pos, setPos] = useState({ top: 0, left: 0 })
  const tRef = useRef<HTMLDivElement>(null); const mRef = useRef<HTMLDivElement>(null)
  const refs = useRef([tRef, mRef]).current; const close = () => setOpen(false)
  useOutside(refs, () => setOpen(false), open)
  const toggle = () => {
    if (open) return setOpen(false)
    const r = tRef.current!.getBoundingClientRect(); const w = 190, h = items.length * 40 + 12
    const up = r.bottom + h + 8 > window.innerHeight && r.top > h + 8
    setPos({ top: up ? r.top - h - 6 : r.bottom + 6, left: align === 'right' ? Math.max(8, r.right - w) : Math.min(r.left, window.innerWidth - w - 8) })
    setOpen(true)
  }
  return (
    <div ref={tRef} className="relative inline-block">
      <div onClick={toggle} aria-haspopup="menu" aria-expanded={open}>{trigger}</div>
      {createPortal(
        <AnimatePresence>
          {open && <motion.div ref={mRef} role="menu" initial={{ opacity: 0, y: -4, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.12 }}
            style={{ position: 'fixed', top: pos.top, left: pos.left, minWidth: 176 }} className="z-[70] rounded-lg border border-line bg-card p-1 shadow-xl">
            <MenuList items={items} onPick={close} /></motion.div>}
        </AnimatePresence>, document.body)}
    </div>
  )
}

export function ContextMenu({ items, children, className }: { items: MenuItem[]; children: ReactNode; className?: string }) {
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null); const ref = useRef<HTMLDivElement>(null)
  const refs = useRef([ref]).current; useOutside(refs, () => setPos(null), !!pos)
  return (
    <div className={className} onContextMenu={(e) => { e.preventDefault(); setPos({ x: Math.min(e.clientX, window.innerWidth - 200), y: Math.min(e.clientY, window.innerHeight - items.length * 40 - 16) }) }}>
      {children}
      <AnimatePresence>
        {pos && <motion.div ref={ref} role="menu" initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.1 }}
          style={{ left: pos.x, top: pos.y }} className="fixed z-50 min-w-44 rounded-lg border border-line bg-card p-1 shadow-xl">
          <MenuList items={items} onPick={() => setPos(null)} /></motion.div>}
      </AnimatePresence>
    </div>
  )
}
