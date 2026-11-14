<template>
  <header class="page-header">
    <div class="page-header__text">
      <p class="tiny">{{ eyebrow }}</p>
      <h1>{{ title }}</h1>
      <p v-if="subtitle" class="page-header__sub">{{ subtitle }}</p>
    </div>
    <div class="page-header__actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<script setup lang="ts">
defineProps<{ eyebrow: string; title: string; subtitle?: string }>()
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  padding-bottom: 14px;
  border-bottom: 2px solid var(--ink);
  flex-wrap: wrap;
}

.page-header__text h1 {
  margin-top: 2px;
}

.page-header__sub {
  margin-top: 6px;
  max-width: 62ch;
  color: var(--ink-2);
  font-size: var(--step-0);
}

.page-header__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

@media (max-width: 767px) {
  .page-header {
    align-items: flex-start;
  }
}
</style>
