import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'

const KEY = 'mebelchi.tokens'
export interface Tokens { access: string; refresh: string }

export const tokenStore = {
  get(): Tokens | null {
    try { return JSON.parse(localStorage.getItem(KEY) || 'null') } catch { return null }
  },
  set(t: Tokens | null) {
    try { t ? localStorage.setItem(KEY, JSON.stringify(t)) : localStorage.removeItem(KEY) } catch { /* storage unavailable */ }
  },
}

export const api = axios.create({ baseURL: '/api/v1', timeout: 30000 })

let onLogout: () => void = () => {}
export const setLogoutHandler = (fn: () => void) => { onLogout = fn }

api.interceptors.request.use((cfg: InternalAxiosRequestConfig) => {
  const t = tokenStore.get()
  if (t?.access) cfg.headers.Authorization = `Bearer ${t.access}`
  return cfg
})

let refreshing: Promise<string | null> | null = null
async function refresh(): Promise<string | null> {
  const t = tokenStore.get()
  if (!t?.refresh) return null
  try {
    const { data } = await axios.post('/api/v1/auth/refresh/', { refresh: t.refresh })
    tokenStore.set({ access: data.access, refresh: data.refresh ?? t.refresh })
    return data.access as string
  } catch { return null }
}

api.interceptors.response.use(r => r, async (err: AxiosError) => {
  const cfg = err.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined
  const isAuthCall = cfg?.url?.includes('/auth/')
  if (err.response?.status === 401 && cfg && !cfg._retry && !isAuthCall) {
    cfg._retry = true
    refreshing ??= refresh().finally(() => { refreshing = null })
    const access = await refreshing
    if (access) { cfg.headers.Authorization = `Bearer ${access}`; return api(cfg) }
    tokenStore.set(null); onLogout()
  }
  return Promise.reject(err)
})

export interface ApiErr { message: string; fields: Record<string, string> }
export function apiError(e: unknown): ApiErr {
  const fallback = { message: 'Something went wrong. Please try again.', fields: {} }
  if (!axios.isAxiosError(e)) return fallback
  if (!e.response) return { message: 'Cannot reach the server. Check your connection.', fields: {} }
  const d = e.response.data
  const err = d?.error
  const raw = err?.fields ?? (typeof d === 'object' ? d : {})
  const fields: Record<string, string> = {}
  if (raw && typeof raw === 'object') for (const [k, v] of Object.entries(raw)) {
    if (k === 'detail' || k === 'error') continue
    fields[k] = Array.isArray(v) ? String(v[0]) : typeof v === 'string' ? v : JSON.stringify(v)
  }
  const message = err?.detail && err.detail !== 'Validation failed.' ? err.detail : d?.detail ?? Object.values(fields)[0] ?? (e.response.status === 429 ? 'Too many requests. Please wait a moment.' : fallback.message)
  return { message, fields }
}

export async function downloadBlob(url: string, filename: string, method: 'get' | 'post' = 'get', body?: unknown) {
  const res = await api.request({ url, method, data: body, responseType: 'blob' })
  const href = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = href; a.download = filename; document.body.appendChild(a); a.click(); a.remove()
  setTimeout(() => URL.revokeObjectURL(href), 1000)
}
