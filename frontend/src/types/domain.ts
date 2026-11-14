import type { MaterialType } from '../constants/enums'

export type CaseStatus = 'pending_docs' | 'archived' | 'exception'
export type AttachmentStatus = 'classified' | 'pending' | 'unknown' | 'archived' | 'duplicate'
export type RunStatus = 'queued' | 'running' | 'succeeded' | 'failed'
export type RunMode = 'dry_run' | 'archive'
export type InsuranceType = 'medical' | 'critical' | 'accident' | 'auto' | 'life'

export interface MaterialRef {
  material_type: MaterialType
  label: string
}

export interface SignalRow {
  material_type: MaterialType
  label: string
  filename: number
  content: number
  regex: number
  extension: number
  score: number
}

export interface CaseItem {
  id: string
  case_no: string
  policy_no: string
  customer_name: string
  insurance_type: InsuranceType
  insurance_label: string
  status: CaseStatus
  status_label: string
  channel: string
  assignee: string
  incident_date: string | null
  claim_amount: number
  note: string
  attachment_count: number
  archived_count: number
  duplicate_count: number
  pending_count: number
  unknown_count: number
  classified_count: number
  expected_materials: MaterialRef[]
  archived_materials: MaterialRef[]
  missing_materials: MaterialRef[]
  missing_labels: string[]
  attachments?: AttachmentItem[]
  materials?: MaterialType[]
  updated_at: string | null
}

export interface AttachmentItem {
  id: string
  case_id: string | null
  case_no: string
  customer_name: string
  policy_no: string
  policy_source: string
  scan_seq: number
  source_code: string
  original_name: string
  stored_name: string | null
  material_type: MaterialType
  material_label: string
  confidence: number
  status: AttachmentStatus
  status_label: string
  sha256: string
  sha256_short: string
  size_bytes: number
  size_human: string
  ext: string
  doc_date: string | null
  sequence_no: number | null
  duplicate_of: string | null
  manual_note: string
  content_preview: string
  signals: SignalRow[]
  reason: string
  runner_up: string
  suggestions?: SignalRow[]
  case_missing?: string[]
  bound?: boolean
}

export interface RunItem {
  id: string
  run_no: string
  mode: RunMode
  mode_label: string
  status: RunStatus
  status_label: string
  rule_version: number
  template_snapshot: string
  triggered_by_email: string
  note: string
  scanned: number
  new_files: number
  archived: number
  duplicate: number
  pending: number
  unknown: number
  unchanged: number
  failed: number
  manual: number
  auto_named: number
  log: string[]
  started_at: string | null
  finished_at: string | null
  duration_ms: number
  created_at: string | null
  stored_files?: number
}

export interface RuleItem {
  id: string
  version: number
  template: string
  conflict_policy: string
  date_source: string
  is_active: boolean
  note: string
  created_by_email: string
  created_at: string | null
  usage_runs: number
}

export interface RulePreviewRow {
  attachment_id: string
  original_name: string
  material_type: MaterialType
  confidence: number
  policy_no: string
  doc_date: string
  stored_name: string
  sequence_no: number | null
  action: 'archive' | 'duplicate' | 'no_policy' | 'seq_exhausted'
  reason: string
}

export interface CaseSummary {
  case_status: Record<string, number>
  case_total: number
  attachment_status: Record<string, number>
  attachment_total: number
  material_distribution: Array<{ material_type: MaterialType; label: string; count: number }>
  exceptions: Array<{ id: string; case_no: string; customer_name: string; missing_labels: string[]; pending_count: number }>
  exception_total: number
  archived_attachments: number
  duplicate_attachments: number
  pending_attachments: number
  unknown_attachments: number
}

export interface PagedCases {
  items: CaseItem[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface SourceItem {
  code: string
  name: string
  path: string
  note: string
  cycle: string
  label: string
  attachments: number
}

export interface PendingQueue {
  items: AttachmentItem[]
  pending: AttachmentItem[]
  unknown: AttachmentItem[]
  counts: {
    pending: number
    unknown: number
    duplicate: number
    unbound: number
    total: number
  }
  confirmable_types: Array<{ value: MaterialType; label: string }>
}
