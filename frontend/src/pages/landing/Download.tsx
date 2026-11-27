import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Check, Copy, Download as DownloadIcon, ShieldCheck, Smartphone } from 'lucide-react'
import { api } from '../../lib/api'
import { fmtBytes, fmtDate } from '../../lib/format'
import { useT } from '../../lib/i18n'
import type { AndroidReleases } from '../../lib/types'
import { Logo } from '../../components/Logo'
import { Button } from '../../components/ui/Button'
import { LanguageMenu } from '../../components/LanguageMenu'
import { Skeleton } from '../../components/ui/Misc'
import { ThemeToggle } from '../../layouts/AppShell'

/** Public page: the latest published Android build, its checksum, install steps, release notes and the version history. Everything
 *  comes from `GET /app/android/`; when nothing is published the page says so instead of showing a dead button. */
export default function DownloadPage() {
  const t = useT()
  const [copied, setCopied] = useState(false)
  const q = useQuery({ queryKey: ['android-releases'], queryFn: async () => (await api.get<AndroidReleases>('/app/android/')).data })
  const latest = q.data?.latest ?? null
  const older = (q.data?.releases ?? []).filter((r) => r.version_code !== latest?.version_code)

  const copy = async (text: string) => {
    try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000) } catch { /* clipboard may be blocked; the value stays selectable */ }
  }

  return (
    <div className="min-h-screen">
      <header className="glass sticky top-0 z-40 border-b border-line">
        <div className="mx-auto flex h-16 max-w-4xl items-center justify-between px-4 sm:px-6">
          <Logo />
          <div className="flex items-center gap-1.5"><LanguageMenu /><ThemeToggle /></div>
        </div>
      </header>
      <main className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
        <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-fg"><ArrowLeft size={15} />{t('dl.back')}</Link>
        <div className="mt-6 flex items-start gap-4">
          <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-primary/15 text-primary"><Smartphone size={24} /></span>
          <div><h1 className="text-3xl font-bold sm:text-4xl">{t('dl.title')}</h1><p className="mt-2 text-muted">{t('dl.sub')}</p></div>
        </div>

        {q.isLoading && <div className="mt-8 space-y-3" aria-busy="true"><Skeleton className="h-40" /><Skeleton className="h-24" /></div>}

        {q.isError && (
          <div role="alert" className="mt-8 rounded-2xl border border-danger/40 bg-danger/10 p-5">
            <p>{t('dl.error')}</p><Button className="mt-3" variant="secondary" onClick={() => q.refetch()}>{t('dl.retry')}</Button>
          </div>
        )}

        {q.data && !latest && (
          <div className="mt-8 rounded-2xl border border-line bg-card p-6 text-center">
            <h2 className="text-lg font-semibold">{t('dl.none.title')}</h2><p className="mt-2 text-muted">{t('dl.none.body')}</p>
          </div>
        )}

        {latest && (
          <>
            <section className="mt-8 rounded-2xl border border-line bg-card p-6" aria-label={t('dl.version')}>
              <dl className="grid gap-4 sm:grid-cols-3">
                <div><dt className="text-xs uppercase tracking-wide text-muted">{t('dl.version')}</dt><dd className="mt-1 text-xl font-semibold">{latest.version_name}</dd></div>
                <div><dt className="text-xs uppercase tracking-wide text-muted">{t('dl.released')}</dt><dd className="mt-1 text-xl font-semibold">{latest.published_at ? fmtDate(latest.published_at) : '-'}</dd></div>
                <div><dt className="text-xs uppercase tracking-wide text-muted">{t('dl.size')}</dt><dd className="mt-1 text-xl font-semibold">{fmtBytes(latest.size_bytes)}</dd></div>
              </dl>
              <a href={latest.download_url} download className="mt-6 inline-block"><Button size="lg" icon={<DownloadIcon size={18} />}>{t('dl.button')}</Button></a>
              <p className="mt-3 text-sm text-muted">{t('dl.note.own')}</p>

              <div className="mt-6 border-t border-line pt-5">
                <div className="flex items-center gap-2 text-sm font-medium"><ShieldCheck size={16} className="text-primary" />{t('dl.sha')}</div>
                <div className="mt-2 flex items-start gap-2">
                  <code className="min-w-0 flex-1 break-all rounded-lg bg-card2 px-3 py-2 font-mono text-xs" data-testid="sha">{latest.sha256}</code>
                  <Button size="sm" variant="secondary" onClick={() => copy(latest.sha256)} icon={copied ? <Check size={14} /> : <Copy size={14} />}>{copied ? t('dl.copied') : t('dl.copy')}</Button>
                </div>
                <p className="mt-2 text-xs text-muted">{t('dl.verify')}</p>
              </div>
            </section>

            <section className="mt-6 grid gap-6 md:grid-cols-2">
              <div className="rounded-2xl border border-line bg-card p-6">
                <h2 className="text-lg font-semibold">{t('dl.steps')}</h2>
                <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-muted">
                  {['dl.step1', 'dl.step2', 'dl.step3', 'dl.step4'].map((k) => <li key={k}>{t(k)}</li>)}
                </ol>
              </div>
              <div className="rounded-2xl border border-line bg-card p-6">
                <h2 className="text-lg font-semibold">{t('dl.notes')}</h2>
                {/* plain text on purpose: notes are never rendered as HTML */}
                <p className="mt-3 whitespace-pre-line text-sm text-muted">{latest.notes || t('dl.noNotes')}</p>
              </div>
            </section>

            {older.length > 0 && (
              <section className="mt-6 rounded-2xl border border-line bg-card p-6">
                <h2 className="text-lg font-semibold">{t('dl.history')}</h2>
                <ul className="mt-3 divide-y divide-line">
                  {older.map((r) => (
                    <li key={r.version_code} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
                      <span><span className="font-medium">{r.version_name}</span><span className="ml-2 text-muted">{r.published_at ? fmtDate(r.published_at) : ''} · {fmtBytes(r.size_bytes)}</span></span>
                      <a href={r.download_url} download className="text-primary hover:underline" aria-label={`${t('dl.older')} ${r.version_name}`}>{t('dl.older')}</a>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </>
        )}
      </main>
    </div>
  )
}
