import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { motion } from 'framer-motion'
import { Loader2 } from 'lucide-react'
import clsx from 'clsx'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'sm' | 'md' | 'lg'
interface Props extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'onDrag' | 'onDragStart' | 'onDragEnd' | 'onAnimationStart'> {
  variant?: Variant; size?: Size; loading?: boolean; icon?: ReactNode
}
const v: Record<Variant, string> = {
  primary: 'bg-primary text-on-primary hover:bg-primary-hover shadow-[0_8px_24px_-10px_var(--primary)]',
  secondary: 'bg-card2 text-fg border border-line hover:border-muted/50',
  ghost: 'text-muted hover:text-fg hover:bg-card2',
  danger: 'bg-danger/10 text-danger border border-danger/30 hover:bg-danger/20',
}
const s: Record<Size, string> = { sm: 'h-8 px-3 text-[13px] gap-1.5', md: 'h-10 px-4 text-sm gap-2', lg: 'h-12 px-6 text-[15px] gap-2' }

export const Button = forwardRef<HTMLButtonElement, Props>(({ variant = 'primary', size = 'md', loading, icon, children, className, disabled, ...rest }, ref) => (
  <motion.button ref={ref} whileTap={disabled || loading ? undefined : { scale: 0.97 }} transition={{ duration: 0.12 }}
    className={clsx('inline-flex items-center justify-center rounded-lg font-medium transition-colors select-none disabled:opacity-50 disabled:pointer-events-none', v[variant], s[size], className)}
    disabled={disabled || loading} {...rest}>
    {loading ? <Loader2 size={16} className="animate-spin" aria-hidden /> : icon}
    {children}
  </motion.button>
))
Button.displayName = 'Button'
