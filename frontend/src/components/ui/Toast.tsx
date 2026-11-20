import { create } from 'zustand'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react'

type Kind = 'success' | 'error' | 'info'
interface T { id: number; kind: Kind; message: string }
interface S { toasts: T[]; push: (kind: Kind, message: string) => void; dismiss: (id: number) => void }
let n = 0
export const useToasts = create<S>((set, get) => ({
  toasts: [],
  push: (kind, message) => { const id = ++n; set((s) => ({ toasts: [...s.toasts.slice(-3), { id, kind, message }] })); setTimeout(() => get().dismiss(id), kind === 'error' ? 6000 : 3500) },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}))
export const toast = {
  success: (m: string) => useToasts.getState().push('success', m),
  error: (m: string) => useToasts.getState().push('error', m),
  info: (m: string) => useToasts.getState().push('info', m),
}
const icon = { success: <CheckCircle2 size={18} className="text-success" />, error: <AlertTriangle size={18} className="text-danger" />, info: <Info size={18} className="text-primary" /> }

export function Toaster() {
  const { toasts, dismiss } = useToasts()
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[min(92vw,22rem)] flex-col gap-2" role="status" aria-live="polite">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div key={t.id} layout initial={{ opacity: 0, x: 30 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 30 }}
            className="pointer-events-auto flex items-start gap-2.5 rounded-lg border border-line bg-card p-3 text-sm shadow-xl">
            {icon[t.kind]}<p className="flex-1">{t.message}</p>
            <button onClick={() => dismiss(t.id)} aria-label="Dismiss" className="text-muted hover:text-fg"><X size={16} /></button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
