import { motion } from 'framer-motion'
import type { HTMLAttributes, ReactNode } from 'react'
import clsx from 'clsx'

export function Card({ className, children, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={clsx('rounded-[14px] border border-line bg-card', className)} {...rest}>{children}</div>
}
export function HoverCard({ className, children, onClick, as = 'div' }: { className?: string; children: ReactNode; onClick?: () => void; as?: 'div' | 'button' }) {
  const Comp = motion[as]
  return (
    <Comp whileHover={{ y: -3 }} transition={{ duration: 0.18 }} onClick={onClick}
      className={clsx('rounded-[14px] border border-line bg-card text-left transition-colors hover:border-primary/50 hover:bg-card2', onClick && 'cursor-pointer', className)}>
      {children}
    </Comp>
  )
}
export function SectionTitle({ title, action, subtitle }: { title: string; action?: ReactNode; subtitle?: string }) {
  return (
    <div className="mb-4 flex items-end justify-between gap-3">
      <div><h2 className="text-lg font-semibold">{title}</h2>{subtitle && <p className="text-sm text-muted">{subtitle}</p>}</div>{action}
    </div>
  )
}
