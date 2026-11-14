<template>
  <div class="overlay" role="dialog" aria-modal="true" @click.self="$emit('close')">
    <div class="slip-dialog slip-in">
      <div class="slip-dialog__head">
        <div>
          <p class="tiny">人工改判 · {{ attachment.case_no || '未绑定案件' }}</p>
          <h2>把这份材料判成什么？</h2>
        </div>
        <button type="button" class="btn btn--ghost btn--small" @click="$emit('close')">关闭</button>
      </div>

      <div class="slip-dialog__body">
        <div class="dialog-file">
          <span class="tiny">原名</span>
          <span class="mono">{{ attachment.original_name }}</span>
        </div>

        <div class="dialog-grid">
          <div class="field">
            <label for="confirm-material">材料类型</label>
            <select id="confirm-material" v-model="materialType">
              <option v-for="item in types" :key="item.value" :value="item.value">
                {{ item.label }}
              </option>
            </select>
          </div>
          <div class="field field--ruled">
            <label for="confirm-policy">保单号（P + 12 位）</label>
            <input id="confirm-policy" v-model="policyNo" placeholder="P202600000003" maxlength="13" />
          </div>
        </div>

        <div class="field">
          <label for="confirm-note">改判说明</label>
          <input id="confirm-note" v-model="note" placeholder="例：影像所见与出院小结一致，判为诊断书" maxlength="120" />
        </div>

        <div v-if="attachment.signals?.length" class="dialog-signals">
          <p class="tiny">算法 1 的候选（为什么没自动归档）</p>
          <ul>
            <li v-for="row in attachment.signals.slice(0, 3)" :key="row.material_type">
              <span class="mono">{{ row.score.toFixed(2) }}</span>
              <span>{{ row.label }}</span>
              <span class="tiny">文件 {{ row.filename.toFixed(2) }} · 内容 {{ row.content.toFixed(2) }} · 正则 {{ row.regex.toFixed(2) }}</span>
            </li>
          </ul>
        </div>

        <p class="dialog-hint">
          提交后会按当前命名规则生成目标名并落盘；若内容 SHA-256 与已有件相同，则标记重复件、不落盘。
        </p>

        <ErrorNotice v-if="error" :message="error" :retry-label="''" />
      </div>

      <div class="slip-dialog__foot">
        <button type="button" class="btn btn--ghost" @click="$emit('close')">取消</button>
        <button type="button" class="btn btn--seal" :disabled="submitting" @click="submit">
          {{ submitting ? '提交中…' : '确认改判并归档' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { confirmAttachment } from '../../api/attachments'
import type { MaterialType } from '../../constants/enums'
import type { AttachmentItem } from '../../types/domain'
import ErrorNotice from './ErrorNotice.vue'

const props = defineProps<{
  attachment: AttachmentItem
  types: Array<{ value: MaterialType; label: string }>
}>()

const emit = defineEmits<{ close: []; done: [attachment: AttachmentItem] }>()

const materialType = ref<MaterialType>(
  (props.attachment.material_type !== 'unknown'
    ? props.attachment.material_type
    : props.attachment.suggestions?.[0]?.material_type ?? 'diagnosis') as MaterialType,
)
const policyNo = ref(props.attachment.policy_no || '')
const note = ref('')
const submitting = ref(false)
const error = ref('')

async function submit() {
  submitting.value = true
  error.value = ''
  try {
    const result = await confirmAttachment(props.attachment.id, {
      material_type: materialType.value,
      policy_no: policyNo.value.trim().toUpperCase(),
      note: note.value,
    })
    emit('done', result)
  } catch (cause) {
    error.value = (cause as { message?: string }).message ?? '改判失败'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.dialog-file {
  display: flex;
  flex-direction: column;
  gap: 2px;
  border: 1px solid var(--line);
  background: var(--paper-2);
  padding: 8px 12px;
  margin-bottom: 16px;
  word-break: break-all;
}

.dialog-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 14px;
}

.dialog-signals {
  margin-top: 16px;
  border-top: 1px dashed var(--line-strong);
  padding-top: 10px;
}

.dialog-signals ul {
  list-style: none;
  padding: 0;
  margin: 6px 0 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.dialog-signals li {
  display: flex;
  gap: 10px;
  align-items: baseline;
  font-size: var(--step--1);
}

.dialog-hint {
  margin-top: 16px;
  font-size: var(--step--1);
  color: var(--ink-3);
  border-left: 2px solid var(--line-strong);
  padding-left: 10px;
}

.dialog-hint + .error-notice,
.error-notice {
  margin-top: 14px;
}

@media (max-width: 640px) {
  .dialog-grid {
    grid-template-columns: 1fr;
  }
}
</style>
