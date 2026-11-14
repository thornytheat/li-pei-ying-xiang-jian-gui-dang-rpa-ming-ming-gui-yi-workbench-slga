import { defineStore } from 'pinia'
import { fetchCaseDetail, fetchCaseSummary, fetchCases, fetchSources } from '../api/cases'
import type { CaseItem, CaseSummary, SourceItem } from '../types/domain'

interface CasesState {
  summary: CaseSummary | null
  items: CaseItem[]
  total: number
  page: number
  pages: number
  pageSize: number
  status: string
  query: string
  detail: CaseItem | null
  sources: SourceItem[]
  loading: boolean
  detailLoading: boolean
  error: string
}

export const useCasesStore = defineStore('cases', {
  state: (): CasesState => ({
    summary: null,
    items: [],
    total: 0,
    page: 1,
    pages: 1,
    pageSize: 12,
    status: '',
    query: '',
    detail: null,
    sources: [],
    loading: false,
    detailLoading: false,
    error: '',
  }),
  getters: {
    pendingTotal: (state): number => state.summary?.pending_attachments ?? 0,
    exceptionTotal: (state): number => state.summary?.case_status?.exception ?? 0,
    archivedCases: (state): number => state.summary?.case_status?.archived ?? 0,
    pendingCases: (state): number => state.summary?.case_status?.pending_docs ?? 0,
  },
  actions: {
    async loadSummary() {
      try {
        this.summary = await fetchCaseSummary()
      } catch (error) {
        this.error = (error as { message?: string }).message ?? '概览加载失败'
      }
    },
    async loadSources() {
      try {
        const result = await fetchSources()
        this.sources = result.items
      } catch {
        this.sources = []
      }
    },
    async loadCases(patch: { status?: string; query?: string; page?: number } = {}) {
      this.loading = true
      this.error = ''
      if (patch.status !== undefined) this.status = patch.status
      if (patch.query !== undefined) this.query = patch.query
      if (patch.page !== undefined) this.page = patch.page
      try {
        const result = await fetchCases({
          status: this.status,
          q: this.query,
          page: this.page,
          pageSize: this.pageSize,
        })
        this.items = result.items
        this.total = result.total
        this.pages = result.pages
      } catch (error) {
        this.error = (error as { message?: string }).message ?? '案件列表加载失败'
        this.items = []
      } finally {
        this.loading = false
      }
    },
    async loadDetail(caseId: string) {
      this.detailLoading = true
      this.error = ''
      try {
        this.detail = await fetchCaseDetail(caseId)
      } catch (error) {
        this.error = (error as { message?: string }).message ?? '案件详情加载失败'
        this.detail = null
      } finally {
        this.detailLoading = false
      }
    },
  },
})
