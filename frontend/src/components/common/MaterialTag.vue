<template>
  <span class="tag" :title="materialLabel">
    <span class="material-mark mono">{{ materialShort }}</span>
    {{ materialLabel }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { MATERIAL_LABELS, MATERIAL_SHORT, type MaterialType } from '../../constants/enums'

const props = defineProps<{ material: MaterialType }>()
const materialLabel = computed(() => MATERIAL_LABELS[props.material] ?? props.material)
const materialShort = computed(() => MATERIAL_SHORT[props.material] ?? '?')
</script>

<style scoped>
.material-mark {
  display: inline-grid;
  place-items: center;
  width: 18px;
  height: 18px;
  border: 1px solid var(--line-strong);
  border-radius: 2px;
  font-size: 0.64rem;
  color: var(--kraft-deep);
  background: var(--paper-2);
}
</style>
