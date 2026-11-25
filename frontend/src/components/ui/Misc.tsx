import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ChevronLeft, ChevronRight, ChevronRight as Sep } from 'lucide-react'
import clsx from 'clsx'
import { Button } from './Button'

export const Skeleton = ({ className }: { className?: string }) => <div aria-hidden className={clsx('animate-pulse rounded-lg bg-card2', className)} />

export function Progress({ value, tone = 'primary', label }: { value: number; tone?: 'primary' | 'success' | 'warning' | 'danger'; label?: string }) {
  const v = Math.max(0, Math.min(100, value))
  const t = v > 90 && tone === 'primary' ? 'danger' : tone
  const c = { primary: 'bg-primary', success: 'bg-success', warning: 'bg-warning', danger: 'bg-danger' }[t]
  return (
    <div role="progressbar" aria-valuenow={Math.round(v)} aria-valuemin={0} aria-valuemax={100} aria-label={label} className="h-2 w-full overflow-hidden rounded-full bg-card2">
      <div className={clsx('h-full rounded-full transition-all duration-500', c)} style={{ width: `${v}%` }} />
    </div>
  )
}

export function EmptyState({ icon, title, text, action }: { icon: ReactNode; title: string; text?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-[14px] border border-dashed border-line px-6 py-14 text-center">
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-card2 text-muted">{icon}</div>
      <h3 className="text-base font-semibold">{title}</h3>
      {text && <p className="mt-1 max-w-sm text-sm text-muted">{text}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-[14px] border border-danger/30 bg-danger/5 p-5 text-sm">
      <p className="text-danger">{message}</p>{onRetry && <Button size="sm" variant="secondary" className="mt-3" onClick={onRetry}>Try again</Button>}
    </div>
  )
}

export function Breadcrumbs({ items }: { items: { label: string; to?: string }[] }) {
  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-sm text-muted">
      {items.map((it, i) => (
        <span key={it.label} className="flex items-center gap-1">
          {i > 0 && <Sep size={14} aria-hidden />}
          {it.to ? <Link to={it.to} className="hover:text-fg">{it.label}</Link> : <span className="text-fg" aria-current="page">{it.label}</span>}
        </span>
      ))}
    </nav>
  )
}

export function Pagination({ page, count, pageSize, onPage }: { page: number; count: number; pageSize: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(count / pageSize))
  if (pages <= 1) return null
  return (
    <div className="mt-4 flex items-center justify-between text-sm text-muted">
      <span className="num">Page {page} of {pages} · {count} items</span>
      <div className="flex gap-1">
        <Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page"><ChevronLeft size={16} /></Button>
        <Button size="sm" variant="secondary" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Next page"><ChevronRight size={16} /></Button>
      </div>
    </div>
  )
}

export interface Column<T> { key: string; header: string; render: (row: T) => ReactNode; className?: string }
/** `compact` lets the table shrink to the screen (cells wrap) instead of scrolling sideways; use it when the columns hide themselves on small screens. */
export function DataTable<T extends { id: number | string }>({ columns, rows, empty, onRowClick, compact }: { columns: Column<T>[]; rows: T[]; empty?: ReactNode; onRowClick?: (row: T) => void; compact?: boolean }) {
  if (!rows.length && empty) return <>{empty}</>
  return (
    <div className="overflow-x-auto rounded-[14px] border border-line bg-card">
      <table className={clsx('w-full text-sm', !compact && 'min-w-[32rem]')}>
        <thead><tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
          {columns.map((c) => <th key={c.key} scope="col" className={clsx('px-4 py-3 font-medium', c.className)}>{c.header}</th>)}</tr></thead>
        <tbody>{rows.map((r) => (
          <tr key={r.id} onClick={onRowClick ? (e) => { if (!(e.target as HTMLElement).closest('button,a,input,select,textarea,[role=menuitem],[role=switch]')) onRowClick(r) } : undefined}
            className={clsx('border-b border-line/60 last:border-0 hover:bg-card2/60', onRowClick && 'cursor-pointer')}>
            {columns.map((c) => <td key={c.key} className={clsx('px-4 py-3', c.className)}>{c.render(r)}</td>)}</tr>))}</tbody>
      </table>
    </div>
  )
}

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'primary' }) {
  const c = { neutral: 'bg-card2 text-muted', success: 'bg-success/15 text-success', warning: 'bg-warning/15 text-warning', danger: 'bg-danger/15 text-danger', primary: 'bg-primary/15 text-primary' }[tone]
  return <span className={clsx('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium', c)}>{children}</span>
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="rounded-[14px] border border-line bg-card p-4">
      <p className="text-xs text-muted">{label}</p><p className="num mt-1 whitespace-nowrap text-xl font-semibold sm:text-2xl">{value}</p>{hint && <p className="mt-0.5 text-xs text-muted">{hint}</p>}
    </div>
  )
}
