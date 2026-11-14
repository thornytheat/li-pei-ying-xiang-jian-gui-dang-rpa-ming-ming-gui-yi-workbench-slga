<template>
  <div class="back-row">
    <router-link to="/cases" class="back-link mono">← 回到案件工作台</router-link>
    <span class="tiny">抽屉 01 / 案件详情</span>
  </div>

  <ErrorNotice v-if="cases.error" :message="cases.error" detail="案件可能已被移走" @retry="reload" />

  <div v-if="detail" class="stack">
    <header class="case-head">
      <div class="case-head__main">
        <p class="tiny">理赔案件 · {{ detail.insurance_label }} · {{ sourceLabel(detail.channel) }}</p>
        <h1 class="case-head__no mono">{{ detail.case_no }}</h1>
        <p class="case-head__policy mono">保单号 {{ detail.policy_no }}</p>
        <div class="row">
          <StatusStamp :status="detail.status" kind="case" />
          <span class="tag">受理员 {{ detail.assignee }}</span>
          <span class="tag">出险 {{ formatDate(detail.incident_date) }}</span>
          <span class="tag mono">报案金额 {{ formatAmount(detail.claim_amount) }}</span>
        </div>
      </div>
      <div class="case-head__side">
        <p class="tiny">客户</p>
        <p class="case-head__customer">{{ detail.customer_name }}</p>
        <p class="tiny">{{ detail.attachment_count }} 件影像 · 已归档 {{ detail.archived_count }} · 重复 {{ detail.duplicate_count }}</p>
        <p v-if="detail.note" class="case-head__note">{{ detail.note }}</p>
      </div>
    </header>

    <section class="materials slip">
      <div class="panel-head">
        <h3>应收材料 <span class="tiny">按险种口径</span></h3>
        <span class="tiny">{{ detail.missing_labels.length ? '缺 ' + detail.missing_labels.join('、') : '材料齐全' }}</span>
      </div>
      <div class="panel-body">
        <ul class="checklist">
          <li v-for="item in detail.expected_materials" :key="item.material_type" :class="materialState(item.material_type)">
            <span class="checklist__mark mono">{{ markOf(item.material_type) }}</span>
            <span>{{ item.label }}</span>
            <span class="tiny">{{ stateLabel(item.material_type) }}</span>
          </li>
        </ul>
      </div>
    </section>

    <section class="stack">
      <div class="spread">
        <h2>附件与重命名对照</h2>
        <span class="tiny">旧名 → 新名 · 分类依据来自后端算法 1</span>
      </div>

      <p v-if="flash" class="flash mono">{{ flash }}</p>

      <article v-for="att in detail.attachments" :key="att.id" class="attach">
        <div class="attach__side">
          <span class="attach__seq mono">#{{ pad(att.scan_seq) }}</span>
          <MaterialTag :material="att.material_type" />
          <StatusStamp :status="att.status" kind="attachment" />
          <ConfidenceMeter :confidence="att.confidence" />
        </div>

        <div class="attach__main">
          <RenameCompare :original="att.original_name" :stored="att.stored_name" :hash="att.sha256_short" />

          <details class="signals">
            <summary class="signals__summary tiny">
              分类依据 · {{ att.reason || '算法未给出说明' }}
            </summary>
            <div class="signals__body">
              <div v-for="row in att.signals" :key="row.material_type" class="sig">
                <span class="sig__label">{{ row.label }}</span>
                <div class="sig__track">
                  <span
                    v-for="feature in FEATURE_WEIGHTS"
                    :key="feature.key"
                    class="sig__seg"
                    :class="`sig__seg--${feature.key}`"
                    :style="{ width: `${(row[feature.key] ?? 0) * feature.weight * 100}%` }"
                    :title="`${feature.label} ${row[feature.key].toFixed(2)} × ${feature.weight}`"
                  ></span>
                </div>
                <span class="mono sig__score">{{ row.score.toFixed(2) }}</span>
              </div>
              <p class="tiny signals__note">
                权重：文件名 0.45 / 内容 0.35 / 正则 0.15 / 扩展名 0.05 · 低于 0.60 转人工
              </p>
            </div>
          </details>

          <p v-if="att.duplicate_of" class="attach__dup tiny">
            与已有件内容 SHA-256 相同，判为重复投递：不落盘、保留原名。
          </p>
          <p v-if="att.manual_note" class="attach__manual tiny">人工记录：{{ att.manual_note }}</p>
        </div>

        <div class="attach__actions">
          <button
            v-if="canEdit && isOpen(att)"
            type="button"
            class="btn btn--ghost btn--small"
            @click="editing = att"
          >
            人工改判
          </button>
          <a
            v-if="isOpen(att)"
            class="tiny"
            href="/pending"
            @click.prevent="router.push('/pending')"
          >
            进待确认队列
          </a>
          <span v-if="att.stored_name" class="attach__ok tiny">落盘完成</span>
        </div>
      </article>

      <EmptyState
        v-if="!detail.attachments?.length"
        title="这案子还没收到件"
        hint="把材料投到共享盘对应文件夹，再跑一次归档批次就会出现在这里。"
      />
    </section>
  </div>

  <div v-else-if="!cases.detailLoading" class="loading-line mono">正在读取案件…</div>

  <ConfirmAttachmentDialog
    v-if="editing"
    :attachment="editing"
    :types="confirmableTypes"
    @close="editing = null"
    @done="onConfirmed"
  />
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ConfidenceMeter from '../components/common/ConfidenceMeter.vue'
import ConfirmAttachmentDialog from '../components/common/ConfirmAttachmentDialog.vue'
import EmptyState from '../components/common/EmptyState.vue'
import ErrorNotice from '../components/common/ErrorNotice.vue'
import MaterialTag from '../components/common/MaterialTag.vue'
import RenameCompare from '../components/common/RenameCompare.vue'
import StatusStamp from '../components/common/StatusStamp.vue'
import { FEATURE_WEIGHTS, MATERIAL_LABELS, SOURCE_LABELS, type MaterialType } from '../constants/enums'
import { useAuthStore } from '../stores/authStore'
import { useCasesStore } from '../stores/casesStore'
import type { AttachmentItem } from '../types/domain'
import { formatAmount, formatDate } from '../utils/format'

const cases = useCasesStore()
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const editing = ref<AttachmentItem | null>(null)
const flash = ref('')

const detail = computed(() => cases.detail)
const canEdit = computed(() => auth.can('attachments:confirm'))
const confirmableTypes = (Object.keys(MATERIAL_LABELS) as MaterialType[])
  .filter((key) => key !== 'unknown')
  .map((key) => ({ value: key, label: MATERIAL_LABELS[key] }))

function pad(value: number): string {
  return String(value).padStart(3, '0')
}

function isOpen(att: AttachmentItem): boolean {
  return att.status === 'pending' || att.status === 'unknown' || att.status === 'classified'
}

function sourceLabel(code: string): string {
  return SOURCE_LABELS[code] ?? code
}

function materialState(material: MaterialType): string {
  const attachments = (detail.value?.attachments ?? []).filter((att) => att.material_type === material)
  if (attachments.some((att) => att.status === 'archived' || att.status === 'duplicate')) return 'is-done'
  if (attachments.some((att) => att.status === 'pending')) return 'is-pending'
  if (attachments.some((att) => att.status === 'unknown')) return 'is-unknown'
  if (attachments.length) return 'is-open'
  return 'is-missing'
}

function markOf(material: MaterialType): string {
  const state = materialState(material)
  if (state === 'is-done') return '✓'
  if (state === 'is-pending') return '?'
  if (state === 'is-open') return '·'
  return '×'
}

function stateLabel(material: MaterialType): string {
  const state = materialState(material)
  if (state === 'is-done') return '已归档'
  if (state === 'is-pending') return '待确认'
  if (state === 'is-unknown') return '未识别'
  if (state === 'is-open') return '已识别待归档'
  return '缺件'
}

async function reload() {
  const caseId = String(route.params.id)
  await cases.loadDetail(caseId)
}

function onConfirmed(att: AttachmentItem) {
  editing.value = null
  flash.value = `已改判 ${att.original_name} → ${att.stored_name ?? '重复件（不落盘）'}`
  reload()
}

watch(
  () => route.params.id,
  () => reload(),
)

onMounted(reload)
</script>

<style scoped>
.back-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.back-link {
  border-bottom: none;
  color: var(--ink-2);
}

.back-link:hover {
  color: var(--seal-blue);
}

.case-head {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr);
  gap: 22px;
  padding: 18px 20px 20px;
  border: 1px solid var(--line-strong);
  border-left: 4px solid var(--kraft);
  background: oklch(95% 0.016 85);
}

.case-head__no {
  font-size: var(--step-3);
  line-height: 1.1;
  letter-spacing: 0.06em;
  margin-top: 2px;
}

.case-head__policy {
  color: var(--ink-2);
  margin: 2px 0 12px;
  letter-spacing: 0.06em;
}

.case-head__side {
  border-left: 1px dashed var(--line-strong);
  padding-left: 18px;
}

.case-head__customer {
  font-size: var(--step-2);
  margin: 2px 0 8px;
}

.case-head__note {
  margin-top: 10px;
  font-size: var(--step--1);
  color: var(--kraft-deep);
}

.checklist {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.checklist li {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--line-strong);
  padding: 6px 12px;
  background: var(--paper-3);
  font-size: var(--step--1);
}

.checklist__mark {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  border: 1px solid currentColor;
  border-radius: 50%;
  font-size: 0.7rem;
}

.checklist li.is-done {
  color: var(--seal-green);
  border-color: var(--seal-green);
  background: var(--seal-green-soft);
}
.checklist li.is-pending {
  color: var(--seal-red);
  border-color: var(--seal-red);
  background: var(--seal-red-soft);
}
.checklist li.is-unknown,
.checklist li.is-missing {
  color: var(--seal-red);
  border-style: dashed;
}
.checklist li.is-open {
  color: var(--ink-2);
}

.checklist li .tiny {
  color: inherit;
  opacity: 0.75;
  text-transform: none;
  letter-spacing: 0;
}

.attach {
  display: grid;
  grid-template-columns: 190px minmax(0, 1fr) 116px;
  gap: 18px;
  padding: 16px 18px;
  border: 1px solid var(--line);
  border-left: 3px solid var(--line-strong);
  background: oklch(95.2% 0.015 86);
  transition: border-color 160ms ease, transform 200ms cubic-bezier(0.22, 1, 0.36, 1);
}

.attach:hover {
  border-left-color: var(--kraft);
  transform: translateX(2px);
}

.attach__side {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: flex-start;
  border-right: 1px dashed var(--line);
  padding-right: 12px;
}

.attach__seq {
  font-size: 0.76rem;
  color: var(--ink-3);
}

.attach__main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.attach__actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-start;
  justify-content: flex-start;
}

.attach__ok {
  color: var(--seal-green);
}

.attach__dup,
.attach__manual {
  color: var(--kraft-deep);
  text-transform: none;
  letter-spacing: 0;
}

.signals {
  border-top: 1px dotted var(--line-strong);
  padding-top: 6px;
}

.signals__summary {
  cursor: pointer;
  color: var(--ink-3);
  text-transform: none;
  letter-spacing: 0;
}

.signals__body {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sig {
  display: grid;
  grid-template-columns: 4.2em minmax(0, 1fr) 2.6em;
  align-items: center;
  gap: 8px;
  font-size: var(--step--1);
}

.sig__label {
  color: var(--ink-2);
}

.sig__track {
  display: flex;
  height: 9px;
  width: 100%;
  background: oklch(90% 0.02 84);
  border: 1px solid var(--line);
}

.sig__seg {
  height: 100%;
}

.sig__seg--filename {
  background: var(--kraft);
}
.sig__seg--content {
  background: oklch(62% 0.055 152);
}
.sig__seg--regex {
  background: var(--seal-blue);
}
.sig__seg--extension {
  background: var(--seal-red);
}

.sig__score {
  text-align: right;
  font-size: 0.76rem;
}

.signals__note {
  margin-top: 4px;
  text-transform: none;
  letter-spacing: 0;
}

.flash {
  font-size: var(--step--1);
  color: var(--seal-green);
  border-left: 2px solid var(--seal-green);
  padding-left: 10px;
  margin: 0;
}

.loading-line {
  padding: 24px 0;
  color: var(--ink-3);
}

@media (max-width: 1080px) {
  .attach {
    grid-template-columns: 160px minmax(0, 1fr);
  }
  .attach__actions {
    grid-column: 1 / -1;
    flex-direction: row;
    align-items: center;
    border-top: 1px dashed var(--line);
    padding-top: 8px;
  }
}

@media (max-width: 860px) {
  .case-head {
    grid-template-columns: minmax(0, 1fr);
  }
  .case-head__side {
    border-left: none;
    border-top: 1px dashed var(--line-strong);
    padding-left: 0;
    padding-top: 12px;
  }
  .attach {
    grid-template-columns: minmax(0, 1fr);
  }
  .attach__side {
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
    border-right: none;
    border-bottom: 1px dashed var(--line);
    padding: 0 0 8px;
  }
}
</style>
