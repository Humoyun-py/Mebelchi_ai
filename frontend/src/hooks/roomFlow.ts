import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, apiError } from '../lib/api'
import type { Page } from '../lib/types'
import type { FlowSummary, FlowView, ItemResult, RoomItem, RoomModel } from '../lib/roomFlow'
import { toast } from '../components/ui/Toast'

const key = (id: number | string) => ['room-flow', Number(id)] as const

export function useActiveFlows() {
  return useQuery({ queryKey: ['room-flows', 'active'], queryFn: async () => (await api.get<Page<FlowSummary>>('/room-flows/', { params: { status: 'active' } })).data })
}

export function useFlow(id: number | null) {
  return useQuery({ queryKey: key(id ?? 0), enabled: id != null, queryFn: async () => (await api.get<FlowView>(`/room-flows/${id}/`)).data })
}

export function useRoomModel(id: number, rev: number | null, enabled: boolean) {
  return useQuery({ queryKey: [...key(id), 'model', rev], enabled: enabled && rev != null, placeholderData: keepPreviousData,
    queryFn: async () => (await api.get<RoomModel>(`/room-flows/${id}/model/`)).data })
}

export function useStartFlow() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: async () => (await api.post<FlowView>('/room-flows/')).data,
    onSuccess: (v) => { qc.setQueryData(key(v.id), v); qc.invalidateQueries({ queryKey: ['room-flows'] }) }, onError: (e) => toast.error(apiError(e).message) })
}

/** Everything that changes a flow returns the new FlowView, so the cache is simply replaced. */
export function useFlowActions(id: number) {
  const qc = useQueryClient()
  const put = (v: FlowView) => { qc.setQueryData(key(id), v); qc.invalidateQueries({ queryKey: ['room-flows'] }) }
  const answer = useMutation({ mutationFn: async (a: { step: string; value: unknown }) => (await api.post<FlowView>(`/room-flows/${id}/answer/`, a)).data, onSuccess: put })
  const back = useMutation({ mutationFn: async () => (await api.post<FlowView>(`/room-flows/${id}/back/`)).data, onSuccess: put, onError: (e) => toast.error(apiError(e).message) })
  const abandon = useMutation({ mutationFn: async () => (await api.post<FlowView>(`/room-flows/${id}/abandon/`)).data, onSuccess: put, onError: (e) => toast.error(apiError(e).message) })
  return { answer, back, abandon }
}

/** Furniture changes carry the revision the user saw. A 409 means another device changed the room: reload it. */
export function useItemActions(id: number, getRev: () => number | null, onConflict: () => void) {
  const qc = useQueryClient()
  const apply = (r: ItemResult) => qc.setQueryData<FlowView>(key(id), (v) => (v ? { ...v, rev: r.rev, items: r.items, warnings: r.warnings } : v))
  const fail = (e: unknown) => {
    const err = apiError(e)
    if (err.fields.code === 'rev_conflict') { onConflict(); qc.invalidateQueries({ queryKey: key(id) }); return }
    toast.error(Object.entries(err.fields).filter(([k]) => k !== 'code').map(([k, v]) => `${k}: ${v}`).join('; ') || err.message)
  }
  const add = useMutation({ mutationFn: async (body: Partial<RoomItem>) => (await api.post<ItemResult>(`/room-flows/${id}/items/`, { ...body, rev: getRev() })).data, onSuccess: apply, onError: fail })
  const update = useMutation({ mutationFn: async (a: { id: string; patch: Partial<RoomItem> }) => (await api.patch<ItemResult>(`/room-flows/${id}/items/${a.id}/`, { ...a.patch, rev: getRev() })).data, onSuccess: apply, onError: fail })
  const remove = useMutation({ mutationFn: async (itemId: string) => (await api.delete<ItemResult>(`/room-flows/${id}/items/${itemId}/`, { params: { rev: getRev() } })).data, onSuccess: apply, onError: fail })
  return { add, update, remove, busy: add.isPending || update.isPending || remove.isPending }
}
