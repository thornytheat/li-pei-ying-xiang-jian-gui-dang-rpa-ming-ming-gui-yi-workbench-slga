<template>
  <PageHeader
    eyebrow="抽屉 02 · 命名规则与归档批次"
    title="模板一改，名字全跟着走"
    subtitle="规则按版本落库；批次执行时把当时的模板快照写进 run，历史批次不会被新模板改写。"
  >
    <template #actions>
      <span v-if="runs.busy" class="tag tag--warn">批次执行中</span>
      <button type="button" class="btn btn--ghost btn--small" :disabled="rules.loading" @click="reload">
        {{ rules.loading ? '刷新中…' : '刷新' }}
      </button>
    </template>
  </PageHeader>

  <ErrorNotice v-if="rules.error" :message="rules.error" @retry="reload" />

  <div class="grid-2">
    <!-- ------------------------------------------------------------ 规则 ---- -->
    <section class="stack">
      <div class="slip">
        <div class="panel-head">
          <h3>
            当前规则
            <span v-if="rules.active" class="tag tag--seal mono">v{{ rules.active.version }}</span>
          </h3>
          <span class="tiny">{{ rules.active?.usage_runs ?? 0 }} 个批次用过</span>
        </div>
        <div class="panel-body stack">
          <p class="template-line mono">{{ rules.active?.template ?? '—' }}</p>
          <ul class="token-list">
            <li v-for="token in TEMPLATE_TOKENS" :key="token" class="tag mono">{{ token }}</li>
          </ul>
          <p class="tiny note-line">
            冲突策略：目标名已存在且 SHA-256 相同 → 重复件不落盘；不同 → 序号递增。无法抽保单号 → 保留原名进待确认。
          </p>

          <div class="field">
            <label for="rule-template">模板编辑（保存即生成新版本）</label>
            <textarea
              id="rule-template"
              v-model="templateInput"
              rows="2"
              class="mono template-input"
              :disabled="!canWriteRule"
              placeholder="{保单号}_{材料类型}_{YYYYMMDD}_{序号:02d}"
            ></textarea>
          </div>
          <div class="row token-insert">
            <button
              v-for="token in TEMPLATE_TOKENS"
              :key="token"
              type="button"
              class="btn btn--ghost btn--small"
              :disabled="!canWriteRule"
              @click="insertToken(token)"
            >
              {{ token }}
            </button>
          </div>
          <div class="field">
            <label for="rule-note">版本备注</label>
            <input id="rule-note" v-model="noteInput" :disabled="!canWriteRule" maxlength="120" placeholder="例：把日期来源改为开票日期" />
          </div>

          <div class="row">
            <button type="button" class="btn btn--ghost btn--small" @click="runPreview">用真实附件预览</button>
            <button type="button" class="btn btn--small" :disabled="!canWriteRule || rules.saving" @click="saveRule">
              {{ rules.saving ? '保存中…' : '保存为新版本' }}
            </button>
            <span v-if="!canWriteRule" class="tiny">当前角色只读，不能改规则版本</span>
          </div>

          <p v-if="saveNote" class="tiny ok-line">{{ saveNote }}</p>
          <ErrorNotice v-if="saveError" :message="saveError" :retry-label="''" />
        </div>
      </div>

      <div v-if="rules.preview" class="slip">
        <div class="panel-head">
          <h3>模板预览</h3>
          <span class="tiny" :class="rules.preview.valid ? 'ok-line' : 'bad-line'">{{ rules.preview.message }}</span>
        </div>
        <div class="panel-body">
          <table class="ledger">
            <thead>
              <tr>
                <th>原名</th>
                <th>类型</th>
                <th>目标名</th>
                <th>判定</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in rules.preview.rows" :key="row.attachment_id">
                <td class="mono small-cell">{{ row.original_name }}</td>
                <td class="tiny">{{ MATERIAL_LABELS[row.material_type] ?? row.material_type }}</td>
                <td class="mono small-cell">{{ row.stored_name || '—' }}</td>
                <td>
                  <span class="tag" :class="row.action === 'archive' ? 'tag--green' : 'tag--red'">
                    {{ row.action === 'archive' ? '可归档' : row.action }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
          <p class="tiny note-line">预览走的是后端 planning 逻辑，不写库、不落盘。</p>
        </div>
      </div>

      <div class="slip">
        <div class="panel-head"><h3>版本历史</h3></div>
        <div class="panel-body">
          <ul class="version-list">
            <li v-for="rule in rules.items" :key="rule.id">
              <span class="mono">v{{ rule.version }}</span>
              <span class="mono version-list__tpl">{{ rule.template }}</span>
              <span class="tiny">{{ rule.created_by_email || 'seed' }}</span>
              <span v-if="rule.is_active" class="tag tag--green">生效中</span>
              <button
                v-else
                type="button"
                class="btn btn--ghost btn--small"
                :disabled="!canWriteRule"
                @click="activate(rule.id)"
              >
                启用
              </button>
            </li>
          </ul>
          <p v-if="!rules.items.length" class="tiny">还没有规则版本。</p>
        </div>
      </div>
    </section>

    <!-- ------------------------------------------------------------ 批次 ---- -->
    <aside class="stack">
      <div class="slip">
        <div class="panel-head">
          <h3>发起归档批次</h3>
          <span class="tiny">扫描 3 个投件源</span>
        </div>
        <div class="panel-body stack">
          <FolderTabs v-model="mode" :tabs="modeTabs" />
          <div class="field">
            <label for="run-note">批次备注</label>
            <input id="run-note" v-model="runNoteInput" maxlength="120" placeholder="例：下午补件批次" />
          </div>
          <div class="row">
            <button
              type="button"
              class="btn btn--seal btn--small"
              :disabled="!canRun || starting || runs.busy"
              @click="startRun"
            >
              {{ starting ? '提交中…' : mode === 'dry_run' ? '跑一次试运行' : '开始正式归档' }}
            </button>
            <span v-if="runNote" class="tiny ok-line">{{ runNote }}</span>
            <span v-if="!canRun" class="tiny">当前角色无权发起批次</span>
          </div>
          <p class="tiny note-line">
            试运行只统计不落盘；正式归档会把副本按模板改名写进归档卷，重复件只标记不落盘。
          </p>
        </div>
      </div>

      <div class="slip">
        <div class="panel-head">
          <h3>批次台账</h3>
          <span class="tiny mono">归档卷 {{ runs.storedFiles }} 件</span>
        </div>
        <div class="panel-body">
          <ul class="run-list">
            <li
              v-for="run in runs.items"
              :key="run.id"
              :class="{ 'is-selected': runs.selected?.id === run.id }"
              @click="runs.select(run)"
            >
              <div class="run-list__top">
                <span class="mono">{{ run.run_no }}</span>
                <StatusStamp :status="run.status" kind="run" />
              </div>
              <div class="run-list__meta tiny">
                <span>{{ run.mode_label }}</span>
                <span>v{{ run.rule_version }}</span>
                <span class="mono">{{ run.triggered_by_email }}</span>
              </div>
              <div class="run-list__counts mono">
                <span>扫 {{ run.scanned }}</span>
                <span>归 {{ run.archived }}</span>
                <span>重 {{ run.duplicate }}</span>
                <span>待 {{ run.pending }}</span>
              </div>
            </li>
          </ul>
          <EmptyState v-if="!runs.items.length" title="还没有批次" :hint="EMPTY_HINTS.runs" />
        </div>
      </div>

      <div v-if="runs.selected" class="slip">
        <div class="panel-head">
          <h3>{{ runs.selected.run_no }}</h3>
          <span class="tiny">{{ runs.selected.mode_label }} · {{ runs.selected.status_label }}</span>
        </div>
        <div class="panel-body stack">
          <dl class="run-counters">
            <div><dt>扫描</dt><dd class="mono">{{ runs.selected.scanned }}</dd></div>
            <div><dt>新增</dt><dd class="mono">{{ runs.selected.new_files }}</dd></div>
            <div><dt>归档</dt><dd class="mono ok-line">{{ runs.selected.archived }}</dd></div>
            <div><dt>重复</dt><dd class="mono bad-line">{{ runs.selected.duplicate }}</dd></div>
            <div><dt>待确认</dt><dd class="mono">{{ runs.selected.pending }}</dd></div>
            <div><dt>未识别</dt><dd class="mono">{{ runs.selected.unknown }}</dd></div>
            <div><dt>未变</dt><dd class="mono">{{ runs.selected.unchanged }}</dd></div>
            <div><dt>人工</dt><dd class="mono">{{ runs.selected.manual }}</dd></div>
          </dl>
          <p class="tiny run-status-line">
            由 {{ runs.selected.triggered_by_email }} 发起 · {{ formatDuration(runs.selected.duration_ms) }} ·
            落盘 {{ runs.selected.stored_files ?? runs.storedFiles }} 个文件
          </p>
          <div class="run-log">
            <p v-for="line in runs.selected.log" :key="line" class="mono">{{ line }}</p>
            <p v-if="!runs.selected.log.length" class="mono muted">（暂无日志）</p>
          </div>
        </div>
      </div>

      <div class="slip">
        <div class="panel-head"><h3>投件源</h3></div>
        <div class="panel-body">
          <ul class="source-list">
            <li v-for="source in sources" :key="source.code">
              <span>{{ source.name }}</span>
              <span class="mono">{{ source.attachments }} 件</span>
              <span class="tiny">{{ source.path }}</span>
            </li>
          </ul>
        </div>
      </div>

      <div v-if="canReadAudit" class="slip">
        <div class="panel-head">
          <h3>最近审计</h3>
          <span class="tiny">audit_logs</span>
        </div>
        <div class="panel-body">
          <ul class="audit-list">
            <li v-for="entry in auditItems" :key="entry.id">
              <span class="mono tiny">{{ entry.action }}</span>
              <span class="tiny">{{ entry.actor_email }}</span>
              <span class="tiny mono">{{ formatDateTime(entry.created_at) }}</span>
            </li>
          </ul>
          <p v-if="!auditItems.length" class="tiny">审计日志读取中或为空。</p>
        </div>
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import EmptyState from '../components/common/EmptyState.vue'
import ErrorNotice from '../components/common/ErrorNotice.vue'
import FolderTabs from '../components/common/FolderTabs.vue'
import type { FolderTab } from '../types/ui'
import PageHeader from '../components/common/PageHeader.vue'
import StatusStamp from '../components/common/StatusStamp.vue'
import { fetchAudit, type AuditEntry } from '../api/audit'
import { EMPTY_HINTS } from '../constants/messages'
import { MATERIAL_LABELS, TEMPLATE_TOKENS } from '../constants/enums'
import { useAsync } from '../hooks/useAsync'
import { useAuthStore } from '../stores/authStore'
import { useCasesStore } from '../stores/casesStore'
import { useRulesStore } from '../stores/rulesStore'
import { useRunsStore } from '../stores/runsStore'
import type { RunMode } from '../types/domain'
import { formatDateTime, formatDuration } from '../utils/format'

const rules = useRulesStore()
const runs = useRunsStore()
const cases = useCasesStore()
const auth = useAuthStore()

const templateInput = ref('')
const noteInput = ref('')
const mode = ref<RunMode>('archive')
const runNoteInput = ref('')
const runNote = ref('')
const starting = ref(false)
const saveNote = ref('')
const saveError = ref('')
const auditItems = ref<AuditEntry[]>([])
const auditTask = useAsync<AuditEntry[]>(async () => (await fetchAudit(10)).items)

const sources = computed(() => cases.sources)
const canWriteRule = computed(() => auth.can('rules:write'))
const canRun = computed(() => auth.can('runs:create'))
const canReadAudit = computed(() => auth.can('audit:read'))

const modeTabs: FolderTab[] = [
  { key: 'dry_run', label: '试运行' },
  { key: 'archive', label: '正式归档' },
]

async function reload() {
  await Promise.all([rules.load(), runs.load(), cases.loadSources()])
  if (!templateInput.value && rules.active) templateInput.value = rules.active.template
  if (canReadAudit.value) {
    auditItems.value = (await auditTask.run()) ?? []
  }
}

function insertToken(token: string) {
  templateInput.value = `${templateInput.value}${token}`
}

async function runPreview() {
  await rules.previewTemplate(templateInput.value || '{保单号}_{材料类型}_{YYYYMMDD}_{序号:02d}')
}

async function saveRule() {
  saveNote.value = ''
  saveError.value = ''
  try {
    await rules.save(templateInput.value, noteInput.value)
    saveNote.value = `已保存，当前生效版本 v${rules.active?.version}`
    noteInput.value = ''
  } catch (error) {
    saveError.value = (error as { message?: string }).message ?? '保存失败'
  }
}

async function activate(ruleId: string) {
  try {
    await rules.activate(ruleId)
    saveNote.value = `已切换回 v${rules.active?.version}`
  } catch (error) {
    saveError.value = (error as { message?: string }).message ?? '启用失败'
  }
}

async function startRun() {
  starting.value = true
  runNote.value = ''
  try {
    const run = await runs.start(mode.value, runNoteInput.value)
    runNote.value = `批次 ${run.run_no} 已提交，处理中…`
  } catch (error) {
    runNote.value = (error as { message?: string }).message ?? '批次发起失败'
  } finally {
    starting.value = false
  }
}

watch(
  () => runs.selected?.status,
  async (status) => {
    if (status === 'succeeded' || status === 'failed') {
      const run = runs.selected
      if (run) {
        runNote.value = `批次 ${run.run_no} ${run.status_label}：扫描 ${run.scanned} · 归档 ${run.archived} · 重复 ${run.duplicate} · 待确认 ${run.pending} · 未识别 ${run.unknown}`
      }
      await cases.loadSources()
    }
  },
)

onMounted(reload)
onBeforeUnmount(() => runs.stopPoll())
</script>

<style scoped>
.template-line {
  font-size: var(--step-1);
  letter-spacing: 0.02em;
  border-bottom: 1px solid var(--kraft);
  padding-bottom: 6px;
  word-break: break-all;
}

.token-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.template-input {
  width: 100%;
  border: 1px solid var(--line-strong);
  background: var(--paper-3);
  padding: 8px 10px;
  resize: vertical;
  outline: none;
}

.template-input:focus {
  border-color: var(--seal-blue);
}

.token-insert {
  gap: 6px;
  margin-top: -8px;
}

.note-line {
  text-transform: none;
  letter-spacing: 0;
  line-height: 1.6;
}

.ok-line {
  color: var(--seal-green);
}
.bad-line {
  color: var(--seal-red);
}

.small-cell {
  font-size: 0.76rem;
  word-break: break-all;
  max-width: 18ch;
}

.version-list,
.run-list,
.source-list,
.audit-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.version-list li {
  display: grid;
  grid-template-columns: 3em minmax(0, 1fr) auto;
  gap: 2px 10px;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--line);
  font-size: var(--step--1);
}

.version-list__tpl {
  font-size: 0.72rem;
  word-break: break-all;
  color: var(--ink-2);
}

.version-list li .tiny {
  grid-column: 2 / 3;
}

.version-list li .tag,
.version-list li button {
  grid-row: 1 / 2;
  grid-column: 3 / 4;
}

.run-list li {
  padding: 9px 0;
  border-bottom: 1px solid var(--line);
  cursor: pointer;
  transition: background 140ms ease;
}

.run-list li:hover {
  background: var(--paper-2);
}

.run-list li.is-selected {
  background: var(--paper-2);
  box-shadow: inset 3px 0 0 var(--kraft);
  padding-left: 8px;
}

.run-list__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.run-list__meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin: 2px 0 4px;
  text-transform: none;
  letter-spacing: 0;
}

.run-list__counts {
  display: flex;
  gap: 12px;
  font-size: 0.72rem;
  color: var(--ink-2);
}

.run-counters {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px 8px;
  margin: 0;
  border-top: 1px solid var(--line-strong);
  border-bottom: 1px solid var(--line-strong);
  padding: 10px 0;
}

.run-counters dt {
  font-size: 0.68rem;
  letter-spacing: 0.08em;
  color: var(--ink-3);
}

.run-counters dd {
  margin: 0;
  font-size: var(--step-1);
  line-height: 1.2;
}

.run-status-line {
  text-transform: none;
  letter-spacing: 0;
  line-height: 1.6;
}

.run-log {
  max-height: 190px;
  overflow: auto;
  background: oklch(90.5% 0.02 84);
  border: 1px solid var(--line);
  padding: 8px 10px;
}

.run-log p {
  font-size: 0.7rem;
  line-height: 1.55;
  color: var(--ink-2);
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}

.source-list li {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 1px 10px;
  padding: 7px 0;
  border-bottom: 1px solid var(--line);
  font-size: var(--step--1);
}

.source-list li .tiny {
  grid-column: 1 / -1;
  text-transform: none;
  letter-spacing: 0;
  word-break: break-all;
}

.audit-list li {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 1px 8px;
  padding: 6px 0;
  border-bottom: 1px dotted var(--line);
}

.audit-list li .mono.tiny:first-child {
  color: var(--seal-blue);
}

@media (max-width: 767px) {
  .run-counters {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .version-list li {
    grid-template-columns: 3em minmax(0, 1fr);
  }
  .version-list li .tag,
  .version-list li button {
    grid-row: auto;
    grid-column: 1 / -1;
  }
}
</style>
