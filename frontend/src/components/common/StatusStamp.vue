<template>
  <span class="stamp" :class="variantClass">{{ label }}</span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  ATTACHMENT_STATUS_LABELS,
  CASE_STATUS_LABELS,
  RUN_STATUS_LABELS,
  type AttachmentStatusKey,
  type CaseStatusKey,
  type RunStatusKey,
} from '../../constants/enums'

const props = defineProps<{ status: string; kind: 'case' | 'attachment' | 'run' }>()

const label = computed(() => {
  if (props.kind === 'case') return CASE_STATUS_LABELS[props.status as CaseStatusKey] ?? props.status
  if (props.kind === 'run') return RUN_STATUS_LABELS[props.status as RunStatusKey] ?? props.status
  return ATTACHMENT_STATUS_LABELS[props.status as AttachmentStatusKey] ?? props.status
})

const variantClass = computed(() => {
  if (props.status === 'archived' || props.status === 'succeeded') return 'stamp--green'
  if (props.status === 'exception' || props.status === 'failed' || props.status === 'duplicate') return 'stamp--red'
  if (props.status === 'pending' || props.status === 'pending_docs' || props.status === 'running') return 'stamp--muted'
  return ''
})
</script>
