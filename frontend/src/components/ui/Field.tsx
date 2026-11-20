import { forwardRef, useId, useState, type InputHTMLAttributes, type SelectHTMLAttributes, type TextareaHTMLAttributes, type ReactNode } from 'react'
import { Eye, EyeOff, ChevronDown } from 'lucide-react'
import clsx from 'clsx'

const base = 'peer w-full rounded-lg border bg-card2 px-3.5 text-sm text-fg outline-none transition-colors placeholder-transparent focus:border-primary focus:ring-4 focus:ring-primary/20'
const labelCls = 'pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 bg-transparent px-1 text-sm text-muted transition-all peer-focus:top-0 peer-focus:text-xs peer-focus:text-primary peer-focus:bg-card2 peer-[:not(:placeholder-shown)]:top-0 peer-[:not(:placeholder-shown)]:text-xs peer-[:not(:placeholder-shown)]:bg-card2 rounded'

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> { label: string; error?: string; hint?: string; suffix?: ReactNode }

export const Input = forwardRef<HTMLInputElement, FieldProps>(({ label, error, hint, suffix, type = 'text', className, id, ...rest }, ref) => {
  const uid = useId(); const fid = id ?? uid
  const [show, setShow] = useState(false)
  const isPw = type === 'password'
  return (
    <div className={className}>
      <div className="relative">
        <input ref={ref} id={fid} type={isPw && show ? 'text' : type} placeholder=" " aria-invalid={!!error} aria-describedby={error ? `${fid}-e` : undefined}
          className={clsx(base, 'h-12', error ? 'border-danger' : 'border-line', (isPw || suffix) && 'pr-14')} {...rest} />
        <label htmlFor={fid} className={labelCls}>{label}</label>
        {isPw && (
          <button type="button" onClick={() => setShow(!show)} aria-label={show ? 'Hide password' : 'Show password'}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-fg">{show ? <EyeOff size={18} /> : <Eye size={18} />}</button>
        )}
        {suffix && !isPw && <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted num">{suffix}</span>}
      </div>
      {error ? <p id={`${fid}-e`} role="alert" className="mt-1.5 text-xs text-danger">{error}</p> : hint ? <p className="mt-1.5 text-xs text-muted">{hint}</p> : null}
    </div>
  )
})
Input.displayName = 'Input'

/** Compact labelled number input for editor side panels. */
export function NumberField({ label, value, onChange, unit, min, max, step = 1, error }: {
  label: string; value: number; onChange: (n: number) => void; unit?: string; min?: number; max?: number; step?: number; error?: string
}) {
  const id = useId()
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-xs font-medium text-muted">{label}</label>
      <div className="relative">
        <input id={id} type="number" inputMode="decimal" value={Number.isFinite(value) ? value : ''} min={min} max={max} step={step}
          onChange={(e) => onChange(e.target.value === '' ? NaN : Number(e.target.value))} aria-invalid={!!error}
          className={clsx('num h-9 w-full rounded-lg border bg-card2 px-3 pr-10 text-sm text-fg outline-none focus:border-primary focus:ring-4 focus:ring-primary/20', error ? 'border-danger' : 'border-line')} />
        {unit && <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted">{unit}</span>}
      </div>
      {error && <p role="alert" className="mt-1 text-xs text-danger">{error}</p>}
    </div>
  )
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string; error?: string }>(({ label, error, className, ...rest }, ref) => {
  const id = useId()
  return (
    <div className={className}>
      <div className="relative">
        <textarea ref={ref} id={id} placeholder=" " rows={3} className={clsx(base, 'min-h-24 resize-y py-3.5', error ? 'border-danger' : 'border-line')} {...rest} />
        <label htmlFor={id} className={clsx(labelCls, '!top-5 peer-focus:!top-0 peer-[:not(:placeholder-shown)]:!top-0')}>{label}</label>
      </div>
      {error && <p role="alert" className="mt-1.5 text-xs text-danger">{error}</p>}
    </div>
  )
})
Textarea.displayName = 'Textarea'

export function Select({ label, options, error, className, ...rest }: SelectHTMLAttributes<HTMLSelectElement> & { label: string; options: { value: string | number; label: string }[]; error?: string }) {
  const id = useId()
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1 block text-xs font-medium text-muted">{label}</label>
      <div className="relative">
        <select id={id} className={clsx('h-9 w-full appearance-none rounded-lg border bg-card2 px-3 pr-8 text-sm text-fg outline-none focus:border-primary focus:ring-4 focus:ring-primary/20', error ? 'border-danger' : 'border-line')} {...rest}>
          {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <ChevronDown size={16} className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-muted" aria-hidden />
      </div>
      {error && <p role="alert" className="mt-1 text-xs text-danger">{error}</p>}
    </div>
  )
}

export function Switch({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button type="button" role="switch" aria-checked={checked} aria-label={label} onClick={() => onChange(!checked)}
      className={clsx('relative h-6 w-11 shrink-0 rounded-full transition-colors', checked ? 'bg-primary' : 'bg-line')}>
      <span className={clsx('absolute top-0.5 h-5 w-5 rounded-full bg-white transition-all', checked ? 'left-[22px]' : 'left-0.5')} />
    </button>
  )
}
