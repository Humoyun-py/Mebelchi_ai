import { useEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { X } from 'lucide-react'
import { Button } from './Button'

/** Open modals, innermost last. Only the innermost one reacts to Escape/Tab, and the page scroll lock lasts until the last one closes. */
const stack: symbol[] = []

export function Modal({ open, onClose, title, children, footer, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null)
  // the latest onClose without re-running the effect (re-running would reshuffle the modal stack on every parent render)
  const closeRef = useRef(onClose)
  useEffect(() => { closeRef.current = onClose })
  useEffect(() => {
    if (!open) return
    const prev = document.activeElement as HTMLElement | null
    const me = Symbol('modal'); stack.push(me)
    const onKey = (e: KeyboardEvent) => {
      if (stack[stack.length - 1] !== me) return
      if (e.key === 'Escape') closeRef.current()
      if (e.key === 'Tab' && ref.current) {
        const f = ref.current.querySelectorAll<HTMLElement>('button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])')
        if (!f.length) return
        const first = f[0], last = f[f.length - 1]
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
      }
    }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    // focus the first field, but never steal focus from a field the user (or a script) has already moved to inside the dialog
    const autofocus = setTimeout(() => { if (ref.current && !ref.current.contains(document.activeElement)) ref.current.querySelector<HTMLElement>('input,select,textarea')?.focus() }, 50)
    return () => { clearTimeout(autofocus); document.removeEventListener('keydown', onKey); stack.splice(stack.indexOf(me), 1); if (!stack.length) document.body.style.overflow = ''; prev?.focus() }
  }, [open])
  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-0 backdrop-blur-sm sm:items-center sm:p-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
          <motion.div ref={ref} role="dialog" aria-modal="true" aria-label={title}
            initial={{ opacity: 0, y: 24, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 16 }} transition={{ duration: 0.18 }}
            className={`max-h-[92dvh] w-full overflow-y-auto rounded-t-2xl border border-line bg-card p-5 shadow-2xl sm:rounded-2xl ${wide ? 'sm:max-w-3xl' : 'sm:max-w-md'}`}>
            <div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-semibold">{title}</h2>
              <button onClick={onClose} aria-label="Close" className="rounded-md p-1 text-muted hover:bg-card2 hover:text-fg"><X size={18} /></button></div>
            {children}
            {footer && <div className="mt-5 flex justify-end gap-2">{footer}</div>}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  )
}

export function ConfirmDialog({ open, onClose, onConfirm, title, message, confirmLabel = 'Delete', cancelLabel = 'Cancel', loading }: {
  open: boolean; onClose: () => void; onConfirm: () => void; title: string; message: string; confirmLabel?: string; cancelLabel?: string; loading?: boolean
}) {
  return (
    <Modal open={open} onClose={onClose} title={title}
      footer={<><Button variant="ghost" onClick={onClose}>{cancelLabel}</Button><Button variant="danger" loading={loading} onClick={onConfirm}>{confirmLabel}</Button></>}>
      <p className="text-sm text-muted">{message}</p>
    </Modal>
  )
}
