import type { ReactElement } from 'react'
import { render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { AxiosError, type AxiosResponse } from 'axios'
import { api } from '../lib/api'
import { Toaster } from '../components/ui/Toast'
import { useAuth } from '../stores/auth'
import { useUI } from '../stores/ui'
import type { User } from '../lib/types'

export const makeUser = (over: Partial<User> = {}): User => ({ id: 1, email: 'me@x.com', first_name: 'Me', last_name: 'User', full_name: 'Me User', phone: '', avatar_url: null, role: 'maker', role_selected: true,
  theme: 'dark', language: 'en', notify_email: true, notify_system: true, is_admin: false, date_joined: '2026-01-01T00:00:00Z', ...over })

export function signIn(over: Partial<User> = {}) { useUI.setState({ language: 'en' }); useAuth.setState({ user: makeUser(over), ready: true }) }

/** Renders with a fresh QueryClient (no retries) and a router; `path` is the route pattern the element is mounted on, `url` the location. */
export function renderApp(ui: ReactElement, { url = '/', path = '*', client }: { url?: string; path?: string; client?: QueryClient } = {}) {
  const qc = client ?? new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={qc}><MemoryRouter initialEntries={[url]}><Routes><Route path={path} element={ui} /><Route path="*" element={<div data-testid="elsewhere" />} /></Routes></MemoryRouter><Toaster /></QueryClientProvider>)
}

export const page = <T,>(results: T[], extra: object = {}) => ({ count: results.length, next: null, previous: null, results, ...extra })
export const httpError = (status: number, data: unknown) => new AxiosError('x', 'ERR', undefined, undefined, { status, data } as AxiosResponse)

type Handler = unknown | ((cfg?: { params?: Record<string, unknown> }) => unknown)
/** Routes `api.get` by exact URL (longest registered key wins); unknown URLs reject so a forgotten mock is loud, not silent. */
export function routeGet(routes: Record<string, Handler>) {
  vi.mocked(api.get).mockImplementation((async (url: string, cfg?: { params?: Record<string, unknown> }) => {
    const key = Object.keys(routes).filter((k) => url === k).sort((a, b) => b.length - a.length)[0]
    if (!key) throw httpError(404, { error: { status: 404, detail: `unmocked GET ${url}` } })
    const h = routes[key]
    const data = typeof h === 'function' ? (h as (c?: unknown) => unknown)(cfg) : h
    if (data instanceof Error) throw data
    return { data } as never
  }) as never)
}
