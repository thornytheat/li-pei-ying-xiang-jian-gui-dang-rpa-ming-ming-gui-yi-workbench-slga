<template>
  <div class="meter" :class="{ 'meter--low': isLow }">
    <svg viewBox="0 0 120 18" class="meter__svg" role="img" :aria-label="`置信度 ${percent}`">
      <line x1="2" y1="10" x2="118" y2="10" stroke="currentColor" stroke-width="1" opacity="0.35" />
      <g stroke="currentColor" stroke-width="1" opacity="0.5">
        <line v-for="tick in ticks" :key="tick" :x1="2 + tick * 116" y1="6" :x2="2 + tick * 116" y2="14" />
      </g>
      <line
        :x1="2 + threshold * 116"
        y1="1"
        :x2="2 + threshold * 116"
        y2="17"
        stroke="var(--seal-red)"
        stroke-width="1"
        stroke-dasharray="2 2"
        opacity="0.8"
      />
      <circle :cx="2 + clamped * 116" cy="10" r="3.4" fill="currentColor" />
    </svg>
    <span class="meter__value mono">{{ percent }}</span>
    <span class="meter__hint tiny">阈值 {{ threshold.toFixed(2) }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{ confidence: number; threshold?: number }>(), { threshold: 0.6 })

const ticks = Array.from({ length: 11 }, (_, index) => index / 10)
const clamped = computed(() => Math.min(1, Math.max(0, props.confidence)))
const percent = computed(() => clamped.value.toFixed(2))
const isLow = computed(() => clamped.value < props.threshold)
</script>

<style scoped>
.meter {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 2px 8px;
  color: var(--seal-green);
  max-width: 100%;
}

.meter--low {
  color: var(--seal-red);
}

.meter__svg {
  width: 96px;
  height: 18px;
  overflow: visible;
  flex: none;
}

.meter__value {
  font-size: var(--step--1);
  color: var(--ink);
}

.meter__hint {
  letter-spacing: 0;
  white-space: nowrap;
  font-size: 0.64rem;
}
</style>
