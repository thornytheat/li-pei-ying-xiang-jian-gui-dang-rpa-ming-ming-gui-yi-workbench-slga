<template>
  <div class="rename">
    <div class="rename__row">
      <span class="rename__label tiny">原名</span>
      <span class="rename__old mono" :class="{ 'is-dropped': Boolean(stored) }">{{ original }}</span>
    </div>
    <div class="rename__arrow" aria-hidden="true">
      <svg viewBox="0 0 24 12"><path d="M0 6h18M14 1.5 19 6l-5 4.5" fill="none" stroke="currentColor" stroke-width="1.2" /></svg>
    </div>
    <div class="rename__row">
      <span class="rename__label tiny">归档名</span>
      <span v-if="stored" class="rename__new mono">{{ stored }}</span>
      <span v-else class="rename__empty mono">未落盘 · 保留原名</span>
    </div>
    <div class="rename__meta mono">SHA-256 {{ hash }}</div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ original: string; stored?: string | null; hash: string }>(), { stored: null })
</script>

<style scoped>
.rename {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 28px minmax(0, 1fr);
  align-items: center;
  gap: 4px 8px;
  font-size: var(--step--1);
}

.rename__row {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.rename__label {
  color: var(--ink-3);
}

.rename__old {
  word-break: break-all;
  color: var(--ink-2);
}

.rename__old.is-dropped {
  text-decoration: line-through;
  text-decoration-color: var(--seal-red);
  text-decoration-thickness: 1px;
  color: var(--ink-3);
}

.rename__new {
  word-break: break-all;
  color: var(--ink);
  border-bottom: 1px solid var(--kraft);
}

.rename__empty {
  color: var(--seal-red);
  letter-spacing: 0.04em;
}

.rename__arrow {
  color: var(--kraft-deep);
  align-self: end;
  padding-bottom: 4px;
}

.rename__arrow svg {
  width: 24px;
  height: 12px;
}

.rename__meta {
  grid-column: 1 / -1;
  color: var(--ink-3);
  font-size: 0.68rem;
  letter-spacing: 0.04em;
}
</style>
