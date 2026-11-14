import http from './http'
import type { CaseItem, CaseSummary, PagedCases, SourceItem } from '../types/domain'

export async function fetchCaseSummary(): Promise<CaseSummary> {
  const { data } = await http.get<CaseSummary>('/cases/summary')
  return data
}

export async function fetchCases(params: {
  status?: string
  q?: string
  page?: number
  pageSize?: number
}): Promise<PagedCases> {
  const { data } = await http.get<PagedCases>('/cases', {
    params: { status: params.status || '', q: params.q || '', page: params.page ?? 1, page_size: params.pageSize ?? 12 },
  })
  return data
}

export async function fetchCaseDetail(caseId: string): Promise<CaseItem> {
  const { data } = await http.get<CaseItem>(`/cases/${caseId}`)
  return data
}

export async function fetchSources(): Promise<{ items: SourceItem[]; total_attachments: number }> {
  const { data } = await http.get<{ items: SourceItem[]; total_attachments: number }>('/sources')
  return data
}
