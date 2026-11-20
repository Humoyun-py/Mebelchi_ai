import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, apiError } from '../../lib/api'
import type { User } from '../../lib/types'
import { useAuth } from '../../stores/auth'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Field'
import { toast } from '../../components/ui/Toast'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowLeft, ArrowRight, Check } from 'lucide-react'
import { GoogleButton } from '../../components/GoogleButton'
import { useT } from '../../lib/i18n'
import AuthLayout from './AuthLayout'

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
type Errors = Record<string, string>

function useSubmit(fn: () => Promise<void>) {
  const [loading, setLoading] = useState(false); const [formError, setFormError] = useState(''); const [fieldErrors, setFieldErrors] = useState<Errors>({})
  const run = async (e: FormEvent, validate: () => Errors) => {
    e.preventDefault(); setFormError('')
    const v = validate(); setFieldErrors(v); if (Object.keys(v).length) return
    setLoading(true)
    try { await fn() } catch (err) { const a = apiError(err); setFieldErrors(a.fields); setFormError(Object.keys(a.fields).length ? '' : a.message) } finally { setLoading(false) }
  }
  return { loading, formError, fieldErrors, run }
}
const OrDivider = ({ text }: { text: string }) => <div className="my-5 flex items-center gap-3 text-xs text-muted"><span className="h-px flex-1 bg-line" />{text}<span className="h-px flex-1 bg-line" /></div>
const FormError = ({ text }: { text: string }) => text ? <p role="alert" className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">{text}</p> : null

export function Login() {
  const t = useT(); const [email, setEmail] = useState(''); const [password, setPassword] = useState('')
  const setSession = useAuth((s) => s.setSession); const nav = useNavigate(); const [params] = useSearchParams()
  const { loading, formError, fieldErrors, run } = useSubmit(async () => {
    const { data } = await api.post<{ access: string; refresh: string; user: User }>('/auth/login/', { email, password })
    setSession(data.user, { access: data.access, refresh: data.refresh })
    nav(!data.user.role_selected ? '/choose-role' : params.get('next') || '/app', { replace: true })
  })
  return (
    <AuthLayout title={t('auth.welcome')} subtitle={t('auth.welcome.sub')} footer={<>{t('auth.new')} <Link to="/register" className="font-medium text-primary hover:underline">{t('auth.register')}</Link></>}>
      <GoogleButton /><OrDivider text={t('auth.or')} />
      <form className="space-y-4" noValidate onSubmit={(e) => run(e, (): Errors => ({ ...(EMAIL.test(email) ? {} : { email: 'Enter a valid email address.' }), ...(password ? {} : { password: 'Enter your password.' }) }))}>
        <FormError text={formError} />
        <Input label={t('auth.email')} type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} error={fieldErrors.email} />
        <Input label={t('auth.password')} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} error={fieldErrors.password} />
        <div className="text-right"><Link to="/forgot-password" className="text-sm text-primary hover:underline">{t('auth.forgot')}</Link></div>
        <Button type="submit" size="lg" className="w-full" loading={loading}>{t('auth.login')}</Button>
      </form>
    </AuthLayout>
  )
}

function strength(pw: string) {
  let n = 0
  if (pw.length >= 8) n++
  if (pw.length >= 12) n++
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) n++
  if (/\d/.test(pw) && /[^A-Za-z0-9]/.test(pw)) n++
  return pw ? Math.max(1, n) : 0
}

export function Register() {
  const t = useT(); const [step, setStep] = useState(0)
  const [f, setF] = useState({ first_name: '', last_name: '', email: '', phone: '', password: '', confirm_password: '' })
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value })
  const setSession = useAuth((s) => s.setSession); const nav = useNavigate()
  const [errs, setErrs] = useState<Errors>({}); const [formError, setFormError] = useState(''); const [loading, setLoading] = useState(false)
  const v1 = (): Errors => {
    const e: Errors = {}
    if (!f.first_name.trim()) e.first_name = 'Required.'
    if (!f.last_name.trim()) e.last_name = 'Required.'
    if (!EMAIL.test(f.email)) e.email = 'Enter a valid email address.'
    if (f.phone && !/^\+?[0-9\s()-]{7,20}$/.test(f.phone)) e.phone = 'Enter a valid phone number.'
    return e
  }
  const v2 = (): Errors => {
    const e: Errors = {}
    if (f.password.length < 8) e.password = 'Use at least 8 characters.'
    if (f.confirm_password !== f.password) e.confirm_password = 'Passwords do not match.'
    return e
  }
  const next = (e: FormEvent) => { e.preventDefault(); const v = v1(); setErrs(v); if (!Object.keys(v).length) setStep(1) }
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setFormError(''); const v = v2(); setErrs(v); if (Object.keys(v).length) return
    setLoading(true)
    try {
      const { data } = await api.post<{ access: string; refresh: string; user: User }>('/auth/register/', f)
      setSession(data.user, { access: data.access, refresh: data.refresh }, { keepUiLanguage: true }); toast.success('Account created'); nav('/choose-role', { replace: true })
    } catch (err) {
      const a = apiError(err); setErrs(a.fields); setFormError(Object.keys(a.fields).length ? '' : a.message)
      if (a.fields.email || a.fields.first_name || a.fields.last_name || a.fields.phone) setStep(0)
    } finally { setLoading(false) }
  }
  const score = strength(f.password); const labels = ['', t('pw.weak'), t('pw.fair'), t('pw.good'), t('pw.strong')]; const colors = ['', 'bg-danger', 'bg-warning', 'bg-primary', 'bg-success']
  const steps = [t('reg.step1'), t('reg.step2')]
  return (
    <AuthLayout wide title={t('reg.title')} subtitle={t('reg.sub')} footer={<>{t('auth.have')} <Link to="/login" className="font-medium text-primary hover:underline">{t('auth.login')}</Link></>}>
      <ol className="mb-6 flex items-center gap-3" aria-label="Progress">
        {steps.map((label, i) => (
          <li key={label} className="flex flex-1 items-center gap-2">
            <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition-colors ${i < step ? 'bg-success text-white' : i === step ? 'bg-primary text-on-primary' : 'bg-card2 text-muted'}`}>{i < step ? <Check size={14} /> : i + 1}</span>
            <span className={`hidden text-xs sm:block ${i === step ? 'font-medium' : 'text-muted'}`}>{label}</span>
            {i === 0 && <span className="relative ml-1 h-0.5 flex-1 overflow-hidden rounded bg-line"><motion.span className="absolute inset-y-0 left-0 bg-primary" animate={{ width: step > 0 ? '100%' : '0%' }} /></span>}
          </li>))}
      </ol>
      <AnimatePresence mode="wait" initial={false}>
        {step === 0 ? (
          <motion.form key="s0" initial={{ opacity: 0, x: -24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -24 }} transition={{ duration: 0.2 }} className="space-y-4" noValidate onSubmit={next}>
            <GoogleButton /><OrDivider text={t('auth.or')} />
            <div className="grid gap-4 sm:grid-cols-2"><Input label={t('reg.first')} autoComplete="given-name" value={f.first_name} onChange={set('first_name')} error={errs.first_name} /><Input label={t('reg.last')} autoComplete="family-name" value={f.last_name} onChange={set('last_name')} error={errs.last_name} /></div>
            <Input label={t('auth.email')} type="email" autoComplete="email" value={f.email} onChange={set('email')} error={errs.email} />
            <Input label={t('reg.phone')} type="tel" autoComplete="tel" value={f.phone} onChange={set('phone')} error={errs.phone} />
            <Button type="submit" size="lg" className="w-full" icon={undefined}>{t('reg.next')}<ArrowRight size={16} /></Button>
          </motion.form>
        ) : (
          <motion.form key="s1" initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 24 }} transition={{ duration: 0.2 }} className="space-y-4" noValidate onSubmit={submit}>
            <p className="rounded-lg bg-primary/10 px-3 py-2 text-sm">{t('reg.hi')}, <b>{f.first_name}</b>.</p>
            <FormError text={formError} />
            <Input label={t('auth.password')} type="password" autoComplete="new-password" value={f.password} onChange={set('password')} error={errs.password} hint={t('reg.hint')} />
            {f.password && <div aria-live="polite"><div className="flex gap-1.5">{[1, 2, 3, 4].map((i) => <span key={i} className={`h-1.5 flex-1 rounded-full transition-colors ${i <= score ? colors[score] : 'bg-line'}`} />)}</div><p className="mt-1 text-xs text-muted">{labels[score]}</p></div>}
            <Input label={t('reg.confirm')} type="password" autoComplete="new-password" value={f.confirm_password} onChange={set('confirm_password')} error={errs.confirm_password} />
            <div className="flex gap-3"><Button type="button" variant="secondary" size="lg" onClick={() => setStep(0)} aria-label={t('reg.prev')}><ArrowLeft size={16} /></Button><Button type="submit" size="lg" className="flex-1" loading={loading}>{t('reg.create')}</Button></div>
          </motion.form>
        )}
      </AnimatePresence>
    </AuthLayout>
  )
}

export function ForgotPassword() {
  const [email, setEmail] = useState(''); const [sent, setSent] = useState(false)
  const { loading, formError, fieldErrors, run } = useSubmit(async () => { await api.post('/auth/password-reset/', { email }); setSent(true) })
  return (
    <AuthLayout title="Reset your password" subtitle="Enter your email and we will send you a reset link." footer={<Link to="/login" className="font-medium text-primary hover:underline">Back to log in</Link>}>
      {sent ? <p role="status" className="rounded-lg border border-success/30 bg-success/10 p-4 text-sm">If an account exists for <b>{email}</b>, a reset link has been sent. Check your inbox.</p> : (
        <form className="space-y-4" noValidate onSubmit={(e) => run(e, (): Errors => (EMAIL.test(email) ? {} : { email: 'Enter a valid email address.' }))}>
          <FormError text={formError} /><Input label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} error={fieldErrors.email} />
          <Button type="submit" size="lg" className="w-full" loading={loading}>Send reset link</Button></form>)}
    </AuthLayout>
  )
}

export function ResetPassword() {
  const [params] = useSearchParams(); const nav = useNavigate()
  const [pw, setPw] = useState(''); const [pw2, setPw2] = useState('')
  const { loading, formError, fieldErrors, run } = useSubmit(async () => {
    await api.post('/auth/password-reset/confirm/', { uid: params.get('uid'), token: params.get('token'), new_password: pw }); toast.success('Password updated. Please log in.'); nav('/login')
  })
  const invalid = !params.get('uid') || !params.get('token')
  return (
    <AuthLayout title="Choose a new password" subtitle="Use at least 8 characters." footer={<Link to="/login" className="font-medium text-primary hover:underline">Back to log in</Link>}>
      {invalid ? <p role="alert" className="text-sm text-danger">This reset link is incomplete. Request a new one from the forgot password page.</p> : (
        <form className="space-y-4" noValidate onSubmit={(e) => run(e, (): Errors => ({ ...(pw.length >= 8 ? {} : { new_password: 'Use at least 8 characters.' }), ...(pw === pw2 ? {} : { confirm: 'Passwords do not match.' }) }))}>
          <FormError text={formError || fieldErrors.token || ''} />
          <Input label="New password" type="password" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} error={fieldErrors.new_password} />
          <Input label="Confirm password" type="password" autoComplete="new-password" value={pw2} onChange={(e) => setPw2(e.target.value)} error={fieldErrors.confirm} />
          <Button type="submit" size="lg" className="w-full" loading={loading}>Update password</Button></form>)}
    </AuthLayout>
  )
}
