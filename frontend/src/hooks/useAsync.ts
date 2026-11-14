import { ref, type Ref } from 'vue'

export function useAsync<T>(task: () => Promise<T>) {
  const data: Ref<T | null> = ref(null) as Ref<T | null>
  const loading = ref(false)
  const error = ref('')

  async function run(): Promise<T | null> {
    loading.value = true
    error.value = ''
    try {
      data.value = await task()
      return data.value
    } catch (cause) {
      error.value = (cause as { message?: string }).message ?? '操作失败'
      return null
    } finally {
      loading.value = false
    }
  }

  return { data, loading, error, run }
}
