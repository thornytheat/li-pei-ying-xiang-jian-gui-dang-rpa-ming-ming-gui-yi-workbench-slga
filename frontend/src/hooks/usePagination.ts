import { computed, ref } from 'vue'

export function usePagination(totalPages: () => number) {
  const page = ref(1)
  const pages = computed(() => Math.max(1, totalPages()))
  const canPrev = computed(() => page.value > 1)
  const canNext = computed(() => page.value < pages.value)

  function prev() {
    if (canPrev.value) page.value -= 1
  }
  function next() {
    if (canNext.value) page.value += 1
  }
  function reset() {
    page.value = 1
  }
  return { page, pages, canPrev, canNext, prev, next, reset }
}
