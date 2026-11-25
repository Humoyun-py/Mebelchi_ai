import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, apiError } from '../lib/api'
import { toast } from '../components/ui/Toast'
import type { Invitation, Member, Order, Page, Task, Workshop, WorkshopStats } from '../lib/types'

type Params = Record<string, string | number | boolean | undefined>
/** Workshop data is shared: somebody else may have changed it since we last looked. Always refetch when a view appears or the window regains focus,
 *  and poll lists once a minute while the tab is visible (the app-wide default of "fresh for 15 s, never on focus" is for personal data). */
const LIVE = { staleTime: 0, refetchOnMount: 'always', refetchOnWindowFocus: true } as const
const POLL = { ...LIVE, refetchInterval: 60_000 } as const
const clean = (p: Params) => Object.fromEntries(Object.entries(p).filter(([, v]) => v !== undefined && v !== '' && v !== false))

export const useWorkshops = () => useQuery({ ...POLL, queryKey: ['workshops'], queryFn: async () => (await api.get<Page<Workshop>>('/workshops/', { params: { page_size: 100 } })).data })
export const useWorkshop = (id: number | string) => useQuery({ ...LIVE, queryKey: ['workshop', String(id)], queryFn: async () => (await api.get<Workshop>(`/workshops/${id}/`)).data, retry: false })
export const useInvitations = () => useQuery({ ...POLL, queryKey: ['workshop-invitations'], queryFn: async () => (await api.get<Page<Invitation>>('/workshop-invitations/')).data })
export const useWorkshopStats = (id: number, enabled = true) =>
  useQuery({ ...LIVE, queryKey: ['workshop-stats', id], enabled, queryFn: async () => (await api.get<WorkshopStats>(`/workshops/${id}/statistics/`)).data })
export const useMembers = (ws: number, params: Params = {}, enabled = true) =>
  useQuery({ ...LIVE, queryKey: ['members', ws, params], enabled, queryFn: async () => (await api.get<Page<Member>>(`/workshops/${ws}/members/`, { params: { page_size: 100, ...clean(params) } })).data })
export const useOrders = (params: Params) =>
  useQuery({ ...POLL, queryKey: ['orders', params], queryFn: async () => (await api.get<Page<Order>>('/orders/', { params: clean(params) })).data, placeholderData: keepPreviousData })
export const useOrder = (id: number | null) =>
  useQuery({ ...LIVE, queryKey: ['order', id], enabled: id !== null, queryFn: async () => (await api.get<Order>(`/orders/${id}/`)).data })
export const useTasks = (params: Params, enabled = true) =>
  useQuery({ ...POLL, queryKey: ['tasks', params], enabled, queryFn: async () => (await api.get<Page<Task>>('/tasks/', { params: clean(params) })).data, placeholderData: keepPreviousData })
export const useTask = (id: number | null) =>
  useQuery({ ...LIVE, queryKey: ['task', id], enabled: id !== null, queryFn: async () => (await api.get<Task>(`/tasks/${id}/`)).data })

/** Anything that changes workshop data refreshes every view that may show it (lists, details, statistics). */
export function useInvalidateWorkshop() {
  const qc = useQueryClient()
  return () => { for (const k of ['workshops', 'workshop', 'workshop-invitations', 'workshop-stats', 'members', 'orders', 'order', 'tasks', 'task', 'notifications']) qc.invalidateQueries({ queryKey: [k] }) }
}

/** A mutation that shows the server's message on failure and refreshes workshop data on success. */
export function useAction<V, R = unknown>(fn: (v: V) => Promise<R>, opts: { ok?: string; onSuccess?: (r: R) => void; onError?: (e: unknown) => void } = {}) {
  const invalidate = useInvalidateWorkshop()
  return useMutation({
    mutationFn: fn,
    onSuccess: (r) => { invalidate(); if (opts.ok) toast.success(opts.ok); opts.onSuccess?.(r) },
    onError: (e) => { if (opts.onError) opts.onError(e); else toast.error(apiError(e).message) },
  })
}
