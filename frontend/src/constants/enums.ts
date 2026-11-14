/* 共享枚举（前端镜像）。后端定义：backend/src/constants/enums.py
 * 两份必须一致；README「枚举出现位置」列出了全部引用点。 */

export const MATERIAL_TYPES = ['invoice', 'diagnosis', 'id_card', 'bank_card', 'discharge', 'unknown'] as const
export type MaterialType = (typeof MATERIAL_TYPES)[number]

export const MATERIAL_LABELS: Record<MaterialType, string> = {
  invoice: '发票',
  diagnosis: '诊断书',
  id_card: '身份证',
  bank_card: '银行卡',
  discharge: '出院小结',
  unknown: '未识别',
}

export const MATERIAL_SHORT: Record<MaterialType, string> = {
  invoice: '票',
  diagnosis: '诊',
  id_card: '证',
  bank_card: '卡',
  discharge: '院',
  unknown: '？',
}

export const CASE_STATUSES = ['pending_docs', 'archived', 'exception'] as const
export type CaseStatusKey = (typeof CASE_STATUSES)[number]

export const CASE_STATUS_LABELS: Record<CaseStatusKey, string> = {
  pending_docs: '待收件',
  archived: '已归档',
  exception: '异常',
}

export const ATTACHMENT_STATUSES = ['classified', 'pending', 'unknown', 'archived', 'duplicate'] as const
export type AttachmentStatusKey = (typeof ATTACHMENT_STATUSES)[number]

export const ATTACHMENT_STATUS_LABELS: Record<AttachmentStatusKey, string> = {
  classified: '已识别',
  pending: '待确认',
  unknown: '未识别',
  archived: '已归档',
  duplicate: '重复件',
}

export const RUN_STATUSES = ['queued', 'running', 'succeeded', 'failed'] as const
export type RunStatusKey = (typeof RUN_STATUSES)[number]

export const RUN_STATUS_LABELS: Record<RunStatusKey, string> = {
  queued: '排队中',
  running: '执行中',
  succeeded: '已完成',
  failed: '失败',
}

export const RUN_MODES = ['dry_run', 'archive'] as const
export type RunModeKey = (typeof RUN_MODES)[number]

export const RUN_MODE_LABELS: Record<RunModeKey, string> = {
  dry_run: '试运行',
  archive: '正式归档',
}

export const INSURANCE_TYPES = ['medical', 'critical', 'accident', 'auto', 'life'] as const
export type InsuranceTypeKey = (typeof INSURANCE_TYPES)[number]

export const INSURANCE_LABELS: Record<InsuranceTypeKey, string> = {
  medical: '医疗险',
  critical: '重疾险',
  accident: '意外险',
  auto: '车险',
  life: '寿险',
}

export const INSURANCE_SHORT: Record<InsuranceTypeKey, string> = {
  medical: '医',
  critical: '重',
  accident: '意',
  auto: '车',
  life: '寿',
}

export const SOURCE_LABELS: Record<string, string> = {
  shared_drive: '共享盘投件',
  mailbox: '理赔邮箱附件',
  portable: '移动盘补件',
}

export const SOURCE_SHORT: Record<string, string> = {
  shared_drive: '盘',
  mailbox: '邮',
  portable: '移',
}

/* 与后端 FEATURE_WEIGHTS 一致，仅用于图例说明；实际分数由后端回传 */
export const FEATURE_WEIGHTS: Array<{ key: string; label: string; weight: number }> = [
  { key: 'filename', label: '文件名', weight: 0.45 },
  { key: 'content', label: '内容', weight: 0.35 },
  { key: 'regex', label: '正则', weight: 0.15 },
  { key: 'extension', label: '扩展名', weight: 0.05 },
]

export const TEMPLATE_TOKENS = ['{保单号}', '{材料类型}', '{YYYYMMDD}', '{序号:02d}'] as const
