<template>
  <div class="error-notice" role="alert">
    <div class="error-notice__mark mono">!</div>
    <div class="error-notice__body">
      <strong>{{ title }}</strong>
      <p>{{ message }}</p>
      <p v-if="detail" class="error-notice__detail mono">{{ detail }}</p>
    </div>
    <button v-if="retryLabel" type="button" class="btn btn--ghost btn--small" @click="$emit('retry')">
      {{ retryLabel }}
    </button>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ message: string; title?: string; detail?: string; retryLabel?: string }>(), {
  title: '这一步没走通',
  detail: '',
  retryLabel: '重试',
})
defineEmits<{ retry: [] }>()
</script>

<style scoped>
.error-notice {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  border: 1px solid var(--seal-red);
  background: var(--seal-red-soft);
  padding: 12px 14px;
  border-radius: 2px;
}

.error-notice__mark {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border: 1px solid var(--seal-red);
  border-radius: 50%;
  color: var(--seal-red);
  flex: none;
}

.error-notice__body {
  flex: 1;
  min-width: 0;
}

.error-notice__body p {
  color: var(--ink-2);
  font-size: var(--step--1);
  margin-top: 2px;
}

.error-notice__detail {
  color: var(--ink-3);
  word-break: break-all;
}
</style>
