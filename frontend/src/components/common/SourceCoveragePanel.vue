<template>
  <div class="coverage">
    <div class="coverage__head">
      <span class="coverage__title">投件源读取覆盖</span>
      <span v-if="!hasRows" class="tiny">该批次未记录来源读取</span>
      <span v-else-if="coverage.all_covered" class="tag tag--green">三来源已全部核对</span>
      <span v-else class="tag tag--red">
        {{ coverage.covered_sources }}/{{ coverage.total_sources }} 覆盖 · {{ coverage.failed_sources }} 个来源失败
      </span>
    </div>

    <ul v-if="hasRows" class="coverage__list">
      <li v-for="row in coverage.sources" :key="row.source_code" class="coverage__item" :class="`is-${row.status}`">
        <div class="coverage__row">
          <span class="coverage__name">{{ row.name || fallbackName(row.source_code) }}</span>
          <span class="tag" :class="statusClass(row.status)">{{ row.status_label }}</span>
        </div>
        <p class="tiny coverage__metric">
          读取 <span class="mono">{{ row.read_count }}</span> 件
          <span v-if="row.duration_ms" class="coverage__ms">· {{ row.duration_ms }} ms</span>
        </p>
        <p v-if="row.status === 'failed'" class="tiny coverage__reason">
          <span class="coverage__reason-label">{{ row.failure_label || row.failure_reason }}</span>
          <span v-if="row.failure_detail" class="coverage__reason-detail">｜{{ row.failure_detail }}</span>
          <span class="coverage__reason-hint">（未读到的材料不计丢失，恢复后只补本来源）</span>
        </p>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { SOURCE_LABELS } from '../../constants/enums'
import type { SourceCoverage } from '../../types/domain'

const props = defineProps<{ coverage: SourceCoverage | null | undefined }>()

const hasRows = computed<boolean>(() => Array.isArray(props.coverage?.sources) && props.coverage.sources.length > 0)

function fallbackName(code: string): string {
  return SOURCE_LABELS[code] ?? code
}

function statusClass(status: string): string {
  if (status === 'covered') return 'tag--green'
  if (status === 'failed') return 'tag--red'
  return 'tag--warn'
}
</script>

<style scoped>
.coverage__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.coverage__title {
  font-weight: 600;
  letter-spacing: 0.04em;
}

.coverage__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.coverage__item {
  border: 1px solid var(--line);
  border-left-width: 3px;
  padding: 8px 10px;
  background: var(--paper-2);
}

.coverage__item.is-covered {
  border-left-color: var(--seal-green);
}

.coverage__item.is-failed {
  border-left-color: var(--seal-red);
  background: var(--seal-red-soft);
}

.coverage__item.is-pending {
  border-left-color: var(--ink-3);
  border-left-style: dashed;
}

.coverage__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.coverage__name {
  font-size: var(--step--1);
  font-weight: 500;
}

.coverage__metric {
  margin: 4px 0 0;
  color: var(--ink-2);
  text-transform: none;
  letter-spacing: 0;
}

.coverage__ms {
  color: var(--ink-3);
}

.coverage__reason {
  margin: 4px 0 0;
  line-height: 1.55;
  color: var(--seal-red);
  text-transform: none;
  letter-spacing: 0;
}

.coverage__reason-label {
  font-weight: 600;
}

.coverage__reason-detail {
  color: var(--ink-2);
  word-break: break-all;
}

.coverage__reason-hint {
  color: var(--kraft-deep);
}
</style>
