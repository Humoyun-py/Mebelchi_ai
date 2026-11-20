import { useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

export function Tooltip({ label, children, side = 'right' }: { label: string; children: ReactNode; side?: 'right' | 'top' | 'bottom' }) {
  const [open, setOpen] = useState(false)
  const pos = side === 'right' ? 'left-full top-1/2 ml-2 -translate-y-1/2' : side === 'top' ? 'bottom-full left-1/2 mb-2 -translate-x-1/2' : 'top-full left-1/2 mt-2 -translate-x-1/2'
  return (
    <span className="relative inline-flex" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)} onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}>
      {children}
      <AnimatePresence>
        {open && <motion.span role="tooltip" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.1 }}
          className={`pointer-events-none absolute z-50 whitespace-nowrap rounded-md border border-line bg-card2 px-2 py-1 text-xs text-fg shadow-lg ${pos}`}>{label}</motion.span>}
      </AnimatePresence>
    </span>
  )
}
