import { motion } from 'framer-motion'
import { useId, type ReactNode } from 'react'
import clsx from 'clsx'

export function Tabs<T extends string>({ tabs, value, onChange, className }: { tabs: { id: T; label: string; icon?: ReactNode }[]; value: T; onChange: (v: T) => void; className?: string }) {
  const gid = useId()
  return (
    <div role="tablist" className={clsx('inline-flex max-w-full gap-1 overflow-x-auto rounded-lg border border-line bg-card p-1', className)}>
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={clsx('relative flex shrink-0 items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors', value === t.id ? 'text-fg' : 'text-muted hover:text-fg')}>
          {value === t.id && <motion.span layoutId={gid} className="absolute inset-0 rounded-md bg-card2 ring-1 ring-line" transition={{ type: 'spring', duration: 0.35, bounce: 0.15 }} />}
          <span className="relative flex items-center gap-1.5">{t.icon}{t.label}</span>
        </button>
      ))}
    </div>
  )
}
