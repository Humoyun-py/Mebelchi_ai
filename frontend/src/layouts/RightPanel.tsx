import { createPortal } from 'react-dom'
import { useEffect, useState, type ReactNode } from 'react'

/** Pages render <RightPanel> to fill the shell's contextual right panel. */
export function RightPanel({ children }: { children: ReactNode }) {
  const [el, setEl] = useState<HTMLElement | null>(null)
  useEffect(() => { setEl(document.getElementById('right-panel-slot')) }, [])
  return el ? createPortal(children, el) : null
}

export function PanelSection({ title, children }: { title: string; children: ReactNode }) {
  return <section className="border-b border-line px-4 py-4 last:border-0"><h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted">{title}</h3>{children}</section>
}
