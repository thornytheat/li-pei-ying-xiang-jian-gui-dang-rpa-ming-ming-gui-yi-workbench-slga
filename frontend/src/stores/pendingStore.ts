import { defineStore } from 'pinia'
import { confirmAttachment } from '../api/attachments'
import { fetchPendingQueue } from '../api/pending'
import type { MaterialType } from '../constants/enums'
import type { AttachmentItem, PendingQueue } from '../types/domain'

interface PendingState {
  queue: PendingQueue | null
  loading: boolean
  confirming: boolean
  error: string
  lastFixed: AttachmentItem | null
}

export const usePendingStore = defineStore('pending', {
  state: (): PendingState => ({
    queue: null,
    loading: false,
    confirming: false,
    error: '',
    lastFixed: null,
  }),
  getters: {
    counts: (state) => state.queue?.counts ?? { pending: 0, unknown: 0, duplicate: 0, unbound: 0, total: 0 },
  },
  actions: {
    async load() {
      this.loading = true
      this.error = ''
      try {
        this.queue = await fetchPendingQueue()
      } catch (error) {
        this.error = (error as { message?: string }).message ?? '待确认队列加载失败'
      } finally {
        this.loading = false
      }
    },
    async confirm(attachmentId: string, materialType: MaterialType, policyNo: string, note: string) {
      this.confirming = true
      this.error = ''
      try {
        const fixed = await confirmAttachment(attachmentId, {
          material_type: materialType,
          policy_no: policyNo,
          note,
        })
        this.lastFixed = fixed
        await this.load()
        return fixed
      } catch (error) {
        this.error = (error as { message?: string }).message ?? '改判失败'
        throw error
      } finally {
        this.confirming = false
      }
    },
  },
})
