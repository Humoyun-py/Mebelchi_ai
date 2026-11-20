import { create } from 'zustand'
import { api, setLogoutHandler, tokenStore } from '../lib/api'
import type { User } from '../lib/types'
import { useUI } from './ui'

interface AuthState {
  user: User | null; ready: boolean
  setSession: (user: User, tokens: { access: string; refresh: string }, opts?: { keepUiLanguage?: boolean }) => void
  setUser: (u: User) => void
  load: () => Promise<void>
  logout: () => Promise<void>
}

export const useAuth = create<AuthState>((set) => ({
  user: null, ready: false,
  setSession: (user, tokens, opts) => {
    tokenStore.set(tokens)
    const lang = useUI.getState().language
    if (opts?.keepUiLanguage && lang !== user.language) {  // new account: keep the language chosen before signing up
      api.patch('/users/me/', { language: lang }).catch(() => {})
      user = { ...user, language: lang }
    }
    useUI.getState().adoptProfile(user); set({ user, ready: true })
  },
  setUser: (user) => { useUI.getState().adoptProfile(user); set({ user }) },
  load: async () => {
    if (!tokenStore.get()) { set({ ready: true }); return }
    try { const { data } = await api.get<User>('/users/me/'); useUI.getState().adoptProfile(data); set({ user: data, ready: true }) }
    catch { tokenStore.set(null); set({ user: null, ready: true }) }
  },
  logout: async () => {
    const t = tokenStore.get()
    try { if (t) await api.post('/auth/logout/', { refresh: t.refresh }) } catch { /* already invalid */ }
    tokenStore.set(null); set({ user: null })
  },
}))

setLogoutHandler(() => useAuth.setState({ user: null }))
