<template>
  <PageHeader
    eyebrow="抽屉 01 · 案件工作台"
    title="待收件 / 已归档 / 异常"
    subtitle="按案件看材料齐不齐：算法 1 判类型、算法 2 定名字，低置信件单独抽出来等人工。"
  >
    <template #actions>
      <span v-if="runs.busy || starting" class="tag tag--warn">
        <span class="pulse" aria-hidden="true"></span>
        {{ starting ? '批次提交中' : '批次执行中' }}
      </span>
      <button
        type="button"
        class="btn btn--ghost btn--small"
        :disabled="!auth.can('runs:create') || starting || runs.busy"
        :title="auth.can('runs:create') ? '扫描投件源并归档' : '稽核角色只读'"
        @click="startRun('archive')"
      >
        发起正式归档
      </button>
      <button type="button" class="btn btn--small" :disabled="loading" @click="reloadAll">
        {{ loading ? '刷新中…' : '刷新台账' }}
      </button>
    </template>
  </PageHeader>

  <p v-if="runNote" class="run-note mono">{{ runNote }}</p>

  <ErrorNotice v-if="cases.error" :message="cases.error" detail="可能是后端尚未就绪" @retry="reloadAll" />

  <dl class="kpi-rail">
    <div class="kpi">
      <dt>在办案件</dt>
      <dd>{{ summary?.case_total ?? 0 }}</dd>
    </div>
    <div class="kpi">
      <dt>已归档案件</dt>
      <dd>{{ cases.archivedCases }}</dd>
    </div>
    <div class="kpi">
      <dt>待确认附件</dt>
      <dd>{{ cases.pendingTotal }}</dd>
    </div>
    <div class="kpi">
      <dt>重复投递件</dt>
      <dd>{{ summary?.duplicate_attachments ?? 0 }}</dd>
    </div>
    <div class="kpi">
      <dt>影像件总数</dt>
      <dd>{{ summary?.attachment_total ?? 0 }}</dd>
    </div>
  </dl>

  <div class="grid-2">
    <section class="stack">
      <div class="slip">
        <div class="panel-head">
          <h3>案件台账</h3>
          <div class="row">
            <input
              v-model="search"
              class="search-input mono"
              type="search"
              placeholder="案件号 / 保单号 / 客户"
              @keyup.enter="applySearch"
            />
            <button type="button" class="btn btn--ghost btn--small" @click="applySearch">查</button>
          </div>
        </div>

        <div class="tabs-wrap">
          <FolderTabs v-model="tab" :tabs="tabs" @update:model-value="switchTab" />
        </div>

        <div v-if="cases.loading" class="loading-line mono">正在翻抽屉…</div>

        <template v-else>
          <table v-if="cases.items.length" class="ledger">
            <thead>
              <tr>
                <th>案件 / 保单</th>
                <th>客户</th>
                <th>险种</th>
                <th>附件</th>
                <th>缺失材料</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in cases.items"
                :key="item.id"
                class="is-clickable"
                @click="openCase(item.id)"
              >
                <td>
                  <div class="cell-case">
                    <span class="mono">{{ item.case_no }}</span>
                    <span class="tiny mono">…{{ policyTail(item.policy_no) }}</span>
                  </div>
                </td>
                <td>
                  <div class="cell-customer">
                    <span>{{ item.customer_name }}</span>
                    <span class="tiny">{{ item.assignee }} · {{ sourceShort(item.channel) }}</span>
                  </div>
                </td>
                <td><span class="tag">{{ item.insurance_label }}</span></td>
                <td>
                  <div class="cell-count mono">
                    <span>{{ item.archived_count }}/{{ item.attachment_count }}</span>
                    <span v-if="item.pending_count" class="tiny warn-text">待确认 {{ item.pending_count }}</span>
                  </div>
                </td>
                <td>
                  <div v-if="item.missing_labels.length" class="row missing">
                    <span v-for="label in item.missing_labels.slice(0, 2)" :key="label" class="tag tag--red">
                      缺 {{ label }}
                    </span>
                    <span v-if="item.missing_labels.length > 2" class="tiny">+{{ item.missing_labels.length - 2 }}</span>
                  </div>
                  <span v-else class="tiny ok-text">齐全</span>
                </td>
                <td><StatusStamp :status="item.status" kind="case" /></td>
              </tr>
            </tbody>
          </table>

          <EmptyState
            v-else
            title="这个抽屉是空的"
            :hint="search ? EMPTY_HINTS.search : EMPTY_HINTS.cases"
            action-label="清空筛选"
            @action="clearFilters"
          />
        </template>

        <div v-if="cases.pages > 1" class="pager">
          <button type="button" class="btn btn--ghost btn--small" :disabled="!pager.canPrev.value" @click="goPage(pager.page.value - 1)">
            上一页
          </button>
          <span class="mono tiny">第 {{ cases.page }} / {{ cases.pages }} 页 · 共 {{ cases.total }} 案</span>
          <button
            type="button"
            class="btn btn--ghost btn--small"
            :disabled="!pager.canNext.value"
            @click="goPage(pager.page.value + 1)"
          >
            下一页
          </button>
        </div>
      </div>
    </section>

    <aside class="stack">
      <div class="slip">
        <div class="panel-head"><h3>材料类型分布</h3></div>
        <div class="panel-body">
          <DistributionBar v-if="summary" :rows="summary.material_distribution" />
          <p v-else class="tiny">概览尚未加载</p>
        </div>
      </div>

      <div class="slip">
        <div class="panel-head">
          <h3>异常抽屉</h3>
          <span class="tiny">{{ summary?.exception_total ?? 0 }} 案</span>
        </div>
        <div class="panel-body">
          <ul v-if="summary?.exceptions.length" class="exception-list">
            <li v-for="row in summary.exceptions" :key="row.id" @click="openCase(row.id)">
              <span class="mono">{{ row.case_no }}</span>
              <span>{{ row.customer_name }}</span>
              <span class="tiny warn-text">{{ row.missing_labels.join('、') || '待确认件' }}</span>
            </li>
          </ul>
          <p v-else class="tiny">暂无缺件案件。</p>
        </div>
      </div>

      <div class="slip">
        <div class="panel-head"><h3>投件源</h3></div>
        <div class="panel-body">
          <ul class="source-list">
            <li v-for="source in cases.sources" :key="source.code">
              <span class="source-list__name">{{ source.name }}</span>
              <span class="mono source-list__count">{{ source.attachments }}</span>
              <span class="tiny">{{ source.cycle }}</span>
            </li>
          </ul>
        </div>
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import DistributionBar from '../components/common/DistributionBar.vue'
import EmptyState from '../components/common/EmptyState.vue'
import ErrorNotice from '../components/common/ErrorNotice.vue'
import FolderTabs from '../components/common/FolderTabs.vue'
import type { FolderTab } from '../types/ui'
import PageHeader from '../components/common/PageHeader.vue'
import StatusStamp from '../components/common/StatusStamp.vue'
import { usePagination } from '../hooks/usePagination'
import { EMPTY_HINTS } from '../constants/messages'
import { SOURCE_SHORT } from '../constants/enums'
import { useAuthStore } from '../stores/authStore'
import { useCasesStore } from '../stores/casesStore'
import { useRunsStore } from '../stores/runsStore'
import type { RunMode } from '../types/domain'
import { policyTail } from '../utils/format'

const cases = useCasesStore()
const runs = useRunsStore()
const auth = useAuthStore()
const router = useRouter()

const tab = ref('')
const search = ref('')
const pager = usePagination(() => cases.pages)
const starting = ref(false)
const runNote = ref('')

const summary = computed(() => cases.summary)
const loading = computed(() => cases.loading)

const tabs = computed<FolderTab[]>(() => [
  { key: '', label: '全部', count: summary.value?.case_total ?? 0 },
  { key: 'pending_docs', label: '待收件', count: cases.pendingCases },
  { key: 'archived', label: '已归档', count: cases.archivedCases },
  { key: 'exception', label: '异常', count: cases.exceptionTotal },
])

function sourceShort(code: string): string {
  return SOURCE_SHORT[code] ?? code
}

async function reloadAll() {
  await Promise.all([
    cases.loadSummary(),
    cases.loadCases({ status: tab.value, query: search.value, page: 1 }),
    cases.loadSources(),
    runs.load(),
  ])
}

function switchTab(key: string) {
  tab.value = key
  cases.loadCases({ status: key, query: search.value, page: 1 })
}

function applySearch() {
  cases.loadCases({ query: search.value, page: 1 })
}

function clearFilters() {
  search.value = ''
  tab.value = ''
  cases.loadCases({ status: '', query: '', page: 1 })
}

function goPage(page: number) {
  pager.page.value = Math.min(Math.max(1, page), pager.pages.value)
  cases.loadCases({ page: pager.page.value })
}

function openCase(caseId: string) {
  router.push(`/cases/${caseId}`)
}

async function startRun(mode: RunMode) {
  starting.value = true
  runNote.value = ''
  try {
    const run = await runs.start(mode, '案件工作台发起：全量重扫投件源')
    runNote.value = `批次 ${run.run_no} 已提交（${run.mode_label}），完成后台账自动刷新`
  } catch (error) {
    runNote.value = (error as { message?: string }).message ?? '批次发起失败'
  } finally {
    starting.value = false
  }
}

watch(
  () => cases.page,
  (page) => {
    pager.page.value = page
  },
)

watch(
  () => runs.selected?.status,
  async (status) => {
    if (!status) return
    if (status === 'succeeded' || status === 'failed') {
      const run = runs.selected
      if (run) {
        runNote.value = `批次 ${run.run_no} ${run.status_label}：扫描 ${run.scanned} · 归档 ${run.archived} · 重复 ${run.duplicate} · 待确认 ${run.pending} · 未识别 ${run.unknown}`
      }
      await Promise.all([cases.loadSummary(), cases.loadCases({ page: cases.page }), cases.loadSources()])
    }
  },
)

onMounted(reloadAll)
onBeforeUnmount(() => runs.stopPoll())
</script>

<style scoped>
.run-note {
  margin: 0;
  font-size: var(--step--1);
  color: var(--kraft-deep);
  border-left: 2px solid var(--kraft);
  padding-left: 10px;
}

.tabs-wrap {
  padding: 0 18px;
}

.loading-line {
  padding: 22px 18px;
  color: var(--ink-3);
  font-size: var(--step--1);
}

.cell-case,
.cell-customer,
.cell-count {
  display: flex;
  flex-direction: column;
  line-height: 1.4;
}

.cell-case .mono {
  font-size: 0.84rem;
}

.cell-count .warn-text,
.warn-text {
  color: var(--seal-red);
}

.ok-text {
  color: var(--seal-green);
}

.missing {
  gap: 4px;
}

.pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 18px;
  border-top: 1px solid var(--line);
}

.exception-list,
.source-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
}

.exception-list li {
  display: grid;
  grid-template-columns: minmax(0, auto) minmax(0, 1fr);
  gap: 2px 10px;
  padding: 7px 0;
  border-bottom: 1px solid var(--line);
  cursor: pointer;
  font-size: var(--step--1);
}

.exception-list li:hover {
  background: var(--paper-2);
}

.exception-list li .mono {
  font-size: 0.78rem;
}

.exception-list li .tiny {
  grid-column: 1 / -1;
}

.source-list li {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 1px 10px;
  padding: 7px 0;
  border-bottom: 1px solid var(--line);
  font-size: var(--step--1);
}

.source-list li:last-child {
  border-bottom: none;
}

.source-list__name {
  font-weight: 500;
}

.source-list__count {
  font-size: 0.98rem;
  text-align: right;
}

.source-list li .tiny {
  grid-column: 1 / -1;
  text-transform: none;
  letter-spacing: 0;
}

.pulse {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--warn);
  animation: pulse 1.4s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 0.4;
    transform: scale(0.9);
  }
  50% {
    opacity: 1;
    transform: scale(1.1);
  }
}
</style>
