<template>
  <div class="empty">
    <div class="empty__tab mono" aria-hidden="true">EMPTY</div>
    <h3>{{ title }}</h3>
    <p class="empty__hint">{{ hint }}</p>
    <button v-if="actionLabel" type="button" class="btn btn--ghost btn--small" @click="$emit('action')">
      {{ actionLabel }}
    </button>
  </div>
</template>

<script setup lang="ts">
defineProps<{ title: string; hint: string; actionLabel?: string }>()
defineEmits<{ action: [] }>()
</script>

<style scoped>
.empty {
  position: relative;
  padding: 36px 24px 32px;
  text-align: left;
  max-width: 52ch;
}

.empty__tab {
  display: inline-block;
  border: 1px dashed var(--line-strong);
  color: var(--ink-3);
  font-size: 0.66rem;
  letter-spacing: 0.28em;
  padding: 2px 10px;
  margin-bottom: 12px;
}

.empty h3 {
  font-size: var(--step-1);
}

.empty__hint {
  margin: 6px 0 16px;
  color: var(--ink-2);
}
</style>
