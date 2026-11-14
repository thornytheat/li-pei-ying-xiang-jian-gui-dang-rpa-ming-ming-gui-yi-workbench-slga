<template>
  <figure class="dist">
    <svg viewBox="0 0 600 76" class="dist__svg" role="img" aria-label="材料类型分布">
      <g v-for="(segment, index) in segments" :key="segment.material_type">
        <rect
          :x="segment.x"
          y="8"
          :width="segment.width"
          height="26"
          :fill="segment.color"
          stroke="var(--ink)"
          stroke-width="0.6"
          opacity="0.92"
        />
        <text
          v-if="segment.width > 34"
          :x="segment.x + segment.width / 2"
          y="26"
          text-anchor="middle"
          class="dist__count"
        >
          {{ segment.count }}
        </text>
        <text
          :x="Math.min(segment.x + 1, 552)"
          y="52"
          class="dist__label"
        >{{ segment.label }}</text>
        <line :x1="segment.x" y1="8" :x2="segment.x" y2="60" stroke="var(--line-strong)" stroke-width="0.5" />
      </g>
      <line x1="0" y1="34" x2="600" y2="34" stroke="var(--ink)" stroke-width="0.6" opacity="0.4" />
      <line x1="0" y1="60" x2="600" y2="60" stroke="var(--line-strong)" stroke-width="0.6" />
    </svg>
    <figcaption class="tiny">
      按算法 1 的判定结果统计 · 共 {{ total }} 件 · 每段宽度 = 占比
    </figcaption>
  </figure>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { MaterialType } from '../../constants/enums'

const props = defineProps<{ rows: Array<{ material_type: MaterialType; label: string; count: number }> }>()

const COLORS: Record<string, string> = {
  invoice: 'oklch(88% 0.045 82)',
  diagnosis: 'oklch(82% 0.05 66)',
  id_card: 'oklch(74% 0.05 246)',
  bank_card: 'oklch(70% 0.05 152)',
  discharge: 'oklch(78% 0.06 30)',
  unknown: 'oklch(62% 0.02 70)',
}

const total = computed(() => props.rows.reduce((sum, row) => sum + row.count, 0))

const segments = computed(() => {
  const sum = total.value || 1
  let cursor = 0
  return props.rows.map((row) => {
    const width = (row.count / sum) * 600
    const segment = {
      ...row,
      x: cursor,
      width: Math.max(width, row.count > 0 ? 6 : 0),
      color: COLORS[row.material_type] ?? 'oklch(70% 0.02 70)',
    }
    cursor += segment.width
    return segment
  })
})
</script>

<style scoped>
.dist {
  margin: 0;
}

.dist__svg {
  width: 100%;
  height: auto;
  display: block;
}

.dist__count {
  font-family: var(--font-mono);
  font-size: 11px;
  fill: var(--ink);
}

.dist__label {
  font-family: var(--font-serif);
  font-size: 10px;
  fill: var(--ink-2);
}

.dist figcaption {
  margin-top: 4px;
  text-transform: none;
  letter-spacing: 0;
}
</style>
