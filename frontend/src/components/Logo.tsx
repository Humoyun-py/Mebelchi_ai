import { Link } from 'react-router-dom'

export function LogoMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
      <rect width="32" height="32" rx="8" fill="var(--primary)" />
      <path d="M8 24V8h16v16M8 16h16M16 8v16" fill="none" stroke="var(--on-primary)" strokeWidth="2" strokeLinejoin="round" />
    </svg>
  )
}
export function Logo({ to = '/', collapsed }: { to?: string; collapsed?: boolean }) {
  return (
    <Link to={to} className="flex items-center gap-2.5" aria-label="MEBELCHI AI home">
      <LogoMark />{!collapsed && <span className="font-display text-[15px] font-semibold tracking-tight">MEBELCHI <span className="text-primary">AI</span></span>}
    </Link>
  )
}
