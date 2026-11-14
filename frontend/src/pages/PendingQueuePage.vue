<template>
  <PageHeader
    eyebrow="抽屉 03 · 待确认队列"
    title="算法拿不准的，交回给人"
    subtitle="低于 0.60 的按置信度排队；未识别的连材料类型都没有，需要先补保单号再判。"
  >
    <template #actions>
      <button
        type="button"
        class="btn btn--small"
        :disabled="!auth.can('exports:handover') || exporting"
        :title="auth.can('exports:handover') ? '按案件导出 60 行移交清单' : '稽核角色只能导出稽核清单'"
        @click="exportHandover"
      >
        导出移交清单 CSV
      </button>
      <button type="button" class="btn btn--ghost btn--small" :disabled="exporting" @click="exportAudit">
        导出稽核清单 CSV
      </button>
    </template>
  </PageHeader>

  <ErrorNotice v-if="pending.error" :message="pending.error" @retry="reload" />

  <dl class="kpi-rail">
    <div class="kpi">
      <dt>待确认件</dt>
      <dd>{{ counts.pending }}</dd>
    </div>
    <div class="kpi">
      <dt>未识别件</dt>
      <dd>{{ counts.unknown }}</dd>
    </div>
    <div class="kpi">
      <dt>重复投递件</dt>
      <dd>{{ counts.duplicate }}</dd>
    </div>
    <div class="kpi">
      <dt>未绑定案件</dt>
      <dd>{{ counts.unbound }}</dd>
    </div>
    <div class="kpi">
      <dt>队列总量</dt>
      <dd>{{ counts.total }}</dd>
    </div>
  </dl>

  <p v-if="exportNote" class="flash mono">{{ exportNote }}</p>
  <ErrorNotice v-if="exportError" :message="exportError" :retry-label="''" />

  <div class="grid-2">
    <section class="slip">
      <div class="panel-head">
        <h3>人工复核队列</h3>
        <span class="tiny">点「人工改判」补类型与保单号</span>
      </div>

      <div class="tabs-wrap">
        <FolderTabs v-model="tab" :tabs="tabs" />
      </div>

      <div v-if="pending.loading" class="loading-line mono">正在核对置信度…</div>

      <div v-else class="queue">
        <article v-for="att in visibleItems" :key="att.id" class="item">
          <header class="item__head">
            <span class="item__seq mono">#{{ pad(att.scan_seq) }}</span>
            <span class="item__case mono">{{ att.case_no || '未绑定案件' }}</span>
            <StatusStamp :status="att.status" kind="attachment" />
            <span v-if="!att.bound" class="tag tag--red">缺保单号</span>
          </header>

          <RenameCompare :original="att.original_name" :stored="att.stored_name" :hash="att.sha256_short" />

          <div class="item__meta">
            <span class="tiny">来源 {{ sourceLabel(att.source_code) }}</span>
            <span class="tiny mono">{{ att.size_human }}</span>
            <span class="tiny">拍摄/开票 {{ formatDate(att.doc_date) }}</span>
            <span v-if="att.policy_no" class="tiny mono">已抽到 {{ att.policy_no }}</span>
          </div>

          <p class="item__reason">{{ att.reason }}</p>

          <div class="item__signals">
            <span class="tiny">候选</span>
            <span v-for="row in att.signals.slice(0, 2)" :key="row.material_type" class="tag">
              {{ row.label }} <span class="mono">{{ row.score.toFixed(2) }}</span>
            </span>
          </div>

          <div class="row item__actions">
            <ConfidenceMeter :confidence="att.confidence" />
            <button
              type="button"
              class="btn btn--seal btn--small"
              :disabled="!auth.can('attachments:confirm')"
              :title="auth.can('attachments:confirm') ? '判类型并补保单号' : '稽核角色只读'"
              @click="editing = att"
            >
              人工改判
            </button>
            <span v-if="att.case_missing?.length" class="tiny bad-line">该案还缺 {{ att.case_missing.join('、') }}</span>
          </div>
        </article>

        <EmptyState
          v-if="!visibleItems.length"
          title="队列清空了"
          :hint="EMPTY_HINTS.pending"
          action-label="回案件工作台"
          @action="router.push('/cases')"
        />
      </div>
    </section>

    <aside class="stack">
      <div class="slip">
        <div class="panel-head">
          <h3>移交清单口径</h3>
          <span class="tiny">按案件导 60 行</span>
        </div>
        <div class="panel-body">
          <p class="tiny intro">
            移交清单是给理赔系统与稽核抽查的底稿：每个案件一行，带附件数、已归档数、重复件数、缺失材料提示，
            以及本批底稿批次号。
          </p>
          <ol class="columns">
            <li>案件号 / 保单号 / 客户 / 险种</li>
            <li>案件状态 / 投件源 / 受理员</li>
            <li>附件数 / 已归档 / 重复件 / 待确认 / 未识别</li>
            <li>缺失材料（按险种应收口径）</li>
            <li>底稿批次 / 移交时间</li>
          </ol>
          <p class="tiny intro">导出不会改动任何数据，但会写一条 audit_logs。</p>
        </div>
      </div>

      <div class="slip">
        <div class="panel-head"><h3>最近一次改判</h3></div>
        <div class="panel-body">
          <template v-if="pending.lastFixed">
            <p class="mono small-cell">{{ pending.lastFixed.original_name }}</p>
            <p class="tiny">→ {{ pending.lastFixed.stored_name || '重复件（不落盘）' }}</p>
            <p class="tiny">人工记录：{{ pending.lastFixed.manual_note }}</p>
          </template>
          <p v-else class="tiny">本次会话还没有改判记录。</p>
        </div>
      </div>

      <div class="slip">
        <div class="panel-head"><h3>队列规则</h3></div>
        <div class="panel-body">
          <ul class="rules">
            <li><span class="mono">0.60</span> 置信阈值，低于即入队</li>
            <li><span class="mono">unknown</span> 三路特征全零，不自动归档</li>
            <li><span class="mono">SHA-256</span> 相同判重复件，不落盘</li>
            <li><span class="mono">P+12</span> 保单号必须补全才能命名</li>
          </ul>
        </div>
      </div>
    </aside>
  </div>

  <ConfirmAttachmentDialog
    v-if="editing"
    :attachment="editing"
    :types="confirmableTypes"
    @close="editing = null"
    @done="onConfirmed"
  />
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import ConfidenceMeter from '../components/common/ConfidenceMeter.vue'
import ConfirmAttachmentDialog from '../components/common/ConfirmAttachmentDialog.vue'
import EmptyState from '../components/common/EmptyState.vue'
import ErrorNotice from '../components/common/ErrorNotice.vue'
import FolderTabs from '../components/common/FolderTabs.vue'
import type { FolderTab } from '../types/ui'
import PageHeader from '../components/common/PageHeader.vue'
import RenameCompare from '../components/common/RenameCompare.vue'
import StatusStamp from '../components/common/StatusStamp.vue'
import { downloadAudit, downloadHandover } from '../api/exports'
import { MATERIAL_LABELS, SOURCE_LABELS, type MaterialType } from '../constants/enums'
import { EMPTY_HINTS } from '../constants/messages'
import { useAuthStore } from '../stores/authStore'
import { usePendingStore } from '../stores/pendingStore'
import type { AttachmentItem } from '../types/domain'
import { formatDate } from '../utils/format'

const pending = usePendingStore()
const auth = useAuthStore()
const router = useRouter()

const tab = ref('pending')
const editing = ref<AttachmentItem | null>(null)
const exporting = ref(false)
const exportNote = ref('')
const exportError = ref('')

const counts = computed(() => pending.counts)
const confirmableTypes = (Object.keys(MATERIAL_LABELS) as MaterialType[])
  .filter((key) => key !== 'unknown')
  .map((key) => ({ value: key, label: MATERIAL_LABELS[key] }))

const tabs = computed<FolderTab[]>(() => [
  { key: 'pending', label: '待确认', count: counts.value.pending },
  { key: 'unknown', label: '未识别', count: counts.value.unknown },
  { key: 'all', label: '全部', count: counts.value.total },
])

const visibleItems = computed<AttachmentItem[]>(() => {
  const queue = pending.queue
  if (!queue) return []
  if (tab.value === 'pending') return queue.pending
  if (tab.value === 'unknown') return queue.unknown
  return queue.items
})

function pad(value: number): string {
  return String(value).padStart(3, '0')
}

function sourceLabel(code: string): string {
  return SOURCE_LABELS[code] ?? code
}

async function reload() {
  await pending.load()
}

function onConfirmed(att: AttachmentItem) {
  editing.value = null
  exportNote.value = `已改判 ${att.original_name} → ${att.stored_name ?? '重复件（不落盘）'}`
  tab.value = 'pending'
}

async function exportHandover() {
  exporting.value = true
  exportNote.value = ''
  exportError.value = ''
  try {
    const name = await downloadHandover()
    exportNote.value = `已生成 ${name}（60 行，含附件数与缺失材料提示）`
  } catch (error) {
    exportError.value = (error as { message?: string }).message ?? '导出失败'
  } finally {
    exporting.value = false
  }
}

async function exportAudit() {
  exporting.value = true
  exportNote.value = ''
  exportError.value = ''
  try {
    const name = await downloadAudit()
    exportNote.value = `已生成 ${name}`
  } catch (error) {
    exportError.value = (error as { message?: string }).message ?? '导出失败'
  } finally {
    exporting.value = false
  }
}

onMounted(reload)
</script>

<style scoped>
.tabs-wrap {
  padding: 0 18px;
}

.flash {
  font-size: var(--step--1);
  color: var(--seal-green);
  border-left: 2px solid var(--seal-green);
  padding-left: 10px;
  margin: 0;
}

.loading-line {
  padding: 20px 18px;
  color: var(--ink-3);
}

.queue {
  display: flex;
  flex-direction: column;
}

.item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--line);
  transition: background 140ms ease;
}

.item:hover {
  background: oklch(94% 0.02 84 / 0.7);
}

.item__head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.item__seq {
  font-size: 0.74rem;
  color: var(--ink-3);
}

.item__case {
  font-size: 0.84rem;
}

.item__meta {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  text-transform: none;
  letter-spacing: 0;
}

.item__reason {
  font-size: var(--step--1);
  color: var(--ink-2);
  border-left: 2px solid var(--line-strong);
  padding-left: 10px;
}

.item__signals {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.item__actions {
  justify-content: space-between;
  border-top: 1px dashed var(--line);
  padding-top: 8px;
}

.intro {
  text-transform: none;
  letter-spacing: 0;
  line-height: 1.7;
}

.columns {
  margin: 10px 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-size: var(--step--1);
  color: var(--ink-2);
}

.rules {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: var(--step--1);
}

.rules li {
  border-bottom: 1px dotted var(--line);
  padding-bottom: 5px;
}

.small-cell {
  font-size: 0.78rem;
  word-break: break-all;
}
</style>
