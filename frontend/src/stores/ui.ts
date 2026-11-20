import { create } from 'zustand'
import type { User } from '../lib/types'

type Theme = 'dark' | 'light'
type Lang = 'en' | 'uz' | 'ru'
const read = (k: string) => { try { return localStorage.getItem(k) } catch { return null } }
const write = (k: string, v: string) => { try { localStorage.setItem(k, v) } catch { /* ignore */ } }

function apply(theme: Theme) { document.documentElement.dataset.theme = theme }

interface UIState {
  theme: Theme; language: Lang; sidebarCollapsed: boolean; rightPanelOpen: boolean; mobileNavOpen: boolean
  setTheme: (t: Theme) => void; setLanguage: (l: Lang) => void
  toggleSidebar: () => void; toggleRightPanel: () => void; setMobileNav: (v: boolean) => void
  adoptProfile: (u: User) => void
}

const initialTheme: Theme = read('mebelchi.theme') === 'light' ? 'light' : 'dark'
const l = read('mebelchi.lang')
const initialLang: Lang = l === 'uz' || l === 'ru' ? l : 'en'

export const useUI = create<UIState>((set) => ({
  theme: initialTheme, language: initialLang,
  sidebarCollapsed: read('mebelchi.sidebar') === '1', rightPanelOpen: read('mebelchi.right') !== '0', mobileNavOpen: false,
  setTheme: (theme) => { write('mebelchi.theme', theme); apply(theme); set({ theme }) },
  setLanguage: (language) => { write('mebelchi.lang', language); document.documentElement.lang = language; set({ language }) },
  toggleSidebar: () => set((s) => { write('mebelchi.sidebar', s.sidebarCollapsed ? '0' : '1'); return { sidebarCollapsed: !s.sidebarCollapsed } }),
  toggleRightPanel: () => set((s) => { write('mebelchi.right', s.rightPanelOpen ? '0' : '1'); return { rightPanelOpen: !s.rightPanelOpen } }),
  setMobileNav: (mobileNavOpen) => set({ mobileNavOpen }),
  adoptProfile: (u) => { write('mebelchi.theme', u.theme); write('mebelchi.lang', u.language); apply(u.theme); document.documentElement.lang = u.language; set({ theme: u.theme, language: u.language }) },
}))
apply(initialTheme)
