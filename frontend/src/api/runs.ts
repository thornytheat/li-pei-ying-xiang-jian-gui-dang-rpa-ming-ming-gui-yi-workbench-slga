import http from './http'
import type { RunItem, RunMode } from '../types/domain'

export interface RunListResult {
  items: RunItem[]
  stored_files: number
  active: RunItem | null
}

export async function fetchRuns(limit = 20): Promise<RunListResult> {
  const { data } = await http.get<RunListResult>('/runs', { params: { limit } })
  return data
}

export async function createRun(mode: RunMode, note = ''): Promise<RunItem> {
  const { data } = await http.post<RunItem>('/runs', { mode, note })
  return data
}

export async function fetchRun(runId: string): Promise<RunItem> {
  const { data } = await http.get<RunItem>(`/runs/${runId}`)
  return data
}
