import http from './http'

export interface AuditEntry {
  id: string
  action: string
  actor_email: string
  entity_type: string
  entity_id: string
  detail: Record<string, unknown>
  trace_id: string
  created_at: string | null
}

export async function fetchAudit(limit = 40): Promise<{ items: AuditEntry[]; total: number }> {
  const { data } = await http.get<{ items: AuditEntry[]; total: number }>('/audit', { params: { limit } })
  return data
}
