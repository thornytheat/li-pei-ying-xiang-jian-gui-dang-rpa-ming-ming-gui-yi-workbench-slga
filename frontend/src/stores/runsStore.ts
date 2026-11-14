import { defineStore } from 'pinia'
import { createRun, fetchRun, fetchRuns } from '../api/runs'
import type { RunItem, RunMode } from '../types/domain'

interface RunsState {
  items: RunItem[]
  selected: RunItem | null
  storedFiles: number
  loading: boolean
  starting: boolean
  error: string
  pollTimer: number | null
}

export const useRunsStore = defineStore('runs', {
  state: (): RunsState => ({
    items: [],
    selected: null,
    storedFiles: 0,
    loading: false,
    starting: false,
    error: '',
    pollTimer: null,
  }),
  getters: {
    latest: (state): RunItem | null => state.items[0] ?? null,
    busy: (state): boolean =>
      state.items.some((run) => run.status === 'queued' || run.status === 'running'),
  },
  actions: {
    async load() {
      this.loading = true
      this.error = ''
      try {
        const result = await fetchRuns()
        this.items = result.items
        this.storedFiles = result.stored_files
        if (!this.selected && this.items.length) this.selected = this.items[0]
        if (this.selected) {
          const fresh = this.items.find((run) => run.id === this.selected?.id)
          if (fresh) this.selected = fresh
        }
      } catch (error) {
        this.error = (error as { message?: string }).message ?? '批次列表加载失败'
      } finally {
        this.loading = false
      }
    },
    select(run: RunItem | null) {
      this.selected = run
    },
    async start(mode: RunMode, note: string) {
      this.starting = true
      this.error = ''
      try {
        const run = await createRun(mode, note)
        this.selected = run
        await this.load()
        if (run.status === 'queued' || run.status === 'running') this.poll(run.id)
        return run
      } catch (error) {
        this.error = (error as { message?: string }).message ?? '批次发起失败'
        throw error
      } finally {
        this.starting = false
      }
    },
    poll(runId: string) {
      if (this.pollTimer) window.clearTimeout(this.pollTimer)
      const tick = async () => {
        try {
          const run = await fetchRun(runId)
          this.selected = run
          this.items = this.items.map((item) => (item.id === run.id ? run : item))
          if (run.status === 'queued' || run.status === 'running') {
            this.pollTimer = window.setTimeout(tick, 1200)
          } else {
            this.pollTimer = null
            await this.load()
          }
        } catch {
          this.pollTimer = null
        }
      }
      this.pollTimer = window.setTimeout(tick, 900)
    },
    stopPoll() {
      if (this.pollTimer) window.clearTimeout(this.pollTimer)
      this.pollTimer = null
    },
  },
})
