import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import type { Page } from '../lib/types'
import type { RoomBrief, RoomFlow, RoomItem, RoomModel } from '../lib/room'

const key = (id: number | string) => ['room', String(id)]

export const useRoomList = () => useQuery({ queryKey: ['rooms'], queryFn: async () => (await api.get<Page<RoomBrief>>('/rooms/', { params: { page_size: 50 } })).data })

/** Room flows change on every answer, so a stale copy would show the wrong question: always refetch on mount. */
export const useRoomFlow = (id: number | string) => useQuery({ queryKey: key(id), staleTime: 0, retry: false, queryFn: async () => (await api.get<RoomFlow>(`/rooms/${id}/`)).data })

export const useRoomModel = (id: number | string, enabled: boolean, version: string) =>
  useQuery({ queryKey: ['room-model', String(id), version], enabled, queryFn: async () => (await api.get<RoomModel>(`/rooms/${id}/model/`)).data })

/** Every mutation answers with the whole flow; put it straight into the cache so the UI never waits for a second request. */
function useFlowMutation<V>(id: number | string, fn: (v: V) => Promise<RoomFlow>) {
  const qc = useQueryClient()
  return useMutation({ mutationFn: fn, onSuccess: (f) => { qc.setQueryData(key(id), f); qc.invalidateQueries({ queryKey: ['rooms'] }); qc.invalidateQueries({ queryKey: ['designs'] }) } })
}

export const useAnswer = (id: number | string) => useFlowMutation(id, async (v: { step: string; value: unknown }) => (await api.post<RoomFlow>(`/rooms/${id}/answer/`, v)).data)
export const useBack = (id: number | string) => useFlowMutation(id, async () => (await api.post<RoomFlow>(`/rooms/${id}/back/`)).data)
export const useFinish = (id: number | string) => useFlowMutation(id, async () => (await api.post<RoomFlow>(`/rooms/${id}/finish/`)).data)
export const useResetLayout = (id: number | string) => useFlowMutation(id, async () => (await api.post<RoomFlow>(`/rooms/${id}/reset-layout/`)).data)
export const useAddItem = (id: number | string) => useFlowMutation(id, async (body: Partial<RoomItem> & { template: string }) => (await api.post<RoomFlow>(`/rooms/${id}/items/`, body)).data)
export const usePatchItem = (id: number | string) => useFlowMutation(id, async (v: { item: string; body: Partial<RoomItem> }) => (await api.patch<RoomFlow>(`/rooms/${id}/items/${v.item}/`, v.body)).data)
export const useRemoveItem = (id: number | string) => useFlowMutation(id, async (item: string) => (await api.delete<RoomFlow>(`/rooms/${id}/items/${item}/`)).data)

export function useStartRoom() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: async () => (await api.post<RoomFlow>('/rooms/')).data, onSuccess: (f) => { qc.setQueryData(key(f.id), f); qc.invalidateQueries({ queryKey: ['rooms'] }) } })
}
export function useDeleteRoom() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: async (id: number) => { await api.delete(`/rooms/${id}/`) }, onSuccess: () => qc.invalidateQueries({ queryKey: ['rooms'] }) })
}

/** Opens an old interior design in the room designer (the server copies it; the old design is never changed). Safe to repeat: the same flow comes back. */
export function useImportDesign() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: async (design: number) => (await api.post<RoomFlow>('/rooms/import-design/', { design })).data,
    onSuccess: (f) => { qc.setQueryData(key(f.id), f); qc.invalidateQueries({ queryKey: ['rooms'] }); qc.invalidateQueries({ queryKey: ['designs'] }) } })
}
