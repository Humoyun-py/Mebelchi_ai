import { useEffect, useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import type { CabinetInput, CalcResult, GeometryResult, Meta, Page, Project, Template, WorkspaceSummary, Material } from '../lib/types'

/** Debounces by *value* (JSON), not identity: callers often pass fresh objects every render, which would otherwise reset the timer forever. */
export function useDebounced<T>(value: T, ms = 350): T {
  const [v, setV] = useState(value)
  const key = JSON.stringify(value)
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t) }, [key, ms]) // eslint-disable-line react-hooks/exhaustive-deps
  return v
}

export const useSummary = () => useQuery({ queryKey: ['summary'], queryFn: async () => (await api.get<WorkspaceSummary>('/workspace/summary/')).data })
export const useProjects = (params: Record<string, string | number | boolean> = {}) =>
  useQuery({ queryKey: ['projects', params], queryFn: async () => (await api.get<Page<Project>>('/projects/', { params })).data, placeholderData: keepPreviousData })
export const useTemplates = (category?: string) =>
  useQuery({ queryKey: ['templates', category], queryFn: async () => (await api.get<Template[]>('/furniture/templates/', { params: { category } })).data, staleTime: 300000 })
export const useMaterials = () => useQuery({ queryKey: ['materials'], queryFn: async () => (await api.get<Material[]>('/materials/')).data, staleTime: 120000 })

/** Debounced geometry preview. Works without auth (used on the landing page). */
export function useGeometry(input: CabinetInput, color?: string, enabled = true) {
  const d = useDebounced({ input, color }, 300)
  return useQuery({
    queryKey: ['geometry', d], enabled, placeholderData: keepPreviousData, retry: false, staleTime: 60000,
    queryFn: async () => (await api.post<GeometryResult>('/geometry/preview/', { ...d.input, ...(d.color ? { color: d.color } : {}) })).data,
  })
}
export function useCalculation(input: CabinetInput, enabled = true) {
  const d = useDebounced(input, 350)
  return useQuery({ queryKey: ['calc', d], enabled, placeholderData: keepPreviousData, retry: false, staleTime: 60000,
    queryFn: async () => (await api.post<CalcResult>('/calculations/material/', d)).data })
}

/** Business data and marketing content come from the backend (/meta/), never hard-coded in the UI. */
export const useMeta = () => useQuery({ queryKey: ['meta'], queryFn: async () => (await api.get<Meta>('/meta/')).data, staleTime: 600000 })
