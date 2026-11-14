import { onBeforeUnmount, ref } from 'vue'
import { fetchRun } from '../api/runs'
import type { RunItem } from '../types/domain'

/** 轮询单个批次直到终态；用于发起后等待 Celery worker 完成。 */
export function useRunPoll() {
  const run = ref<RunItem | null>(null)
  const polling = ref(false)
  let timer: number | null = null

  function stop() {
    if (timer) window.clearTimeout(timer)
    timer = null
    polling.value = false
  }

  async function poll(runId: string, onDone?: (value: RunItem) => void) {
    stop()
    polling.value = true
    const tick = async () => {
      try {
        const latest = await fetchRun(runId)
        run.value = latest
        if (latest.status === 'queued' || latest.status === 'running') {
          timer = window.setTimeout(tick, 1000)
        } else {
          stop()
          onDone?.(latest)
        }
      } catch {
        stop()
      }
    }
    await tick()
  }

  onBeforeUnmount(stop)
  return { run, polling, poll, stop }
}
