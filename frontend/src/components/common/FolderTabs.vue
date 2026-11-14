<template>
  <div class="folder-tabs" role="tablist">
    <button
      v-for="tab in tabs"
      :key="tab.key"
      type="button"
      role="tab"
      class="folder-tab"
      :aria-selected="tab.key === modelValue"
      @click="$emit('update:modelValue', tab.key)"
    >
      {{ tab.label }}
      <span v-if="tab.count !== undefined" class="tab-count mono">{{ tab.count }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import type { FolderTab } from '../../types/ui'

defineProps<{ tabs: FolderTab[]; modelValue: string }>()
defineEmits<{ 'update:modelValue': [value: string] }>()
</script>
