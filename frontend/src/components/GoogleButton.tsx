import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, apiError } from '../lib/api'
import { useT } from '../lib/i18n'
import type { User } from '../lib/types'
import { useAuth } from '../stores/auth'
import { useUI } from '../stores/ui'
import { toast } from './ui/Toast'

interface GIS { accounts: { id: { initialize: (c: object) => void; renderButton: (el: HTMLElement, o: object) => void } } }
declare global { interface Window { google?: GIS } }

const loadGis = () => new Promise<void>((resolve, reject) => {
  if (window.google?.accounts) return resolve()
  const s = document.createElement('script'); s.src = 'https://accounts.google.com/gsi/client'; s.async = true
  s.onload = () => resolve(); s.onerror = () => reject(new Error('gis')); document.head.appendChild(s)
})

const GLogo = () => (
  <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden><path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.1C12.4 13.6 17.7 9.5 24 9.5z" /><path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.5 5.8c4.4-4.1 7.1-10.1 7.1-17.5z" /><path fill="#FBBC05" d="M10.5 28.7A14.5 14.5 0 0 1 9.5 24c0-1.6.3-3.2.8-4.7l-7.9-6.1A24 24 0 0 0 0 24c0 3.9.9 7.5 2.6 10.8l7.9-6.1z" /><path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.5-5.8c-2.1 1.4-4.8 2.3-8.4 2.3-6.3 0-11.6-4.1-13.5-9.8l-7.9 6.1C6.5 42.6 14.6 48 24 48z" /></svg>
)

/** Google sign-in / sign-up. Renders Google's own button when GOOGLE_CLIENT_ID is configured on the server. */
export function GoogleButton() {
  const t = useT(); const nav = useNavigate(); const setSession = useAuth((s) => s.setSession); const { theme, language } = useUI()
  const box = useRef<HTMLDivElement>(null); const [failed, setFailed] = useState(false)
  const cfg = useQuery({ queryKey: ['auth-config'], queryFn: async () => (await api.get<{ google_client_id: string | null }>('/auth/config/')).data, staleTime: 600000 })
  const cid = cfg.data?.google_client_id

  useEffect(() => {
    if (!cid || !box.current) return
    let dead = false
    loadGis().then(() => {
      if (dead || !box.current || !window.google) return
      window.google.accounts.id.initialize({
        client_id: cid,
        callback: async (resp: { credential: string }) => {
          try {
            const { data } = await api.post<{ access: string; refresh: string; user: User; created: boolean }>('/auth/google/', { credential: resp.credential })
            setSession(data.user, { access: data.access, refresh: data.refresh }, { keepUiLanguage: data.created }); nav(data.user.role_selected ? '/app' : '/choose-role', { replace: true })
          } catch (e) { toast.error(apiError(e).message) }
        },
      })
      box.current.innerHTML = ''
      window.google.accounts.id.renderButton(box.current, { type: 'standard', theme: theme === 'dark' ? 'filled_black' : 'outline', size: 'large', shape: 'rectangular', text: 'continue_with', width: box.current.clientWidth || 360, locale: language })
    }).catch(() => setFailed(true))
    return () => { dead = true }
  }, [cid, theme, language, nav, setSession])

  if (cid && !failed) return <div ref={box} className="flex min-h-11 w-full justify-center" aria-label={t('auth.google')} />
  return (
    <button type="button" onClick={() => toast.info(t('auth.google.off'))}
      className="flex h-11 w-full items-center justify-center gap-3 rounded-lg border border-line bg-card2 text-sm font-medium text-fg transition-colors hover:border-muted/60">
      <GLogo />{t('auth.google')}
    </button>
  )
}
