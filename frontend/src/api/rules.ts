import http from './http'
import type { RuleItem, RulePreviewRow } from '../types/domain'

export interface RuleListResult {
  items: RuleItem[]
  active: RuleItem | null
  tokens: string[]
  required_tokens: string[]
}

export async function fetchRules(): Promise<RuleListResult> {
  const { data } = await http.get<RuleListResult>('/rules')
  return data
}

export async function createRule(payload: {
  template: string
  note?: string
  conflict_policy?: string
  date_source?: string
}): Promise<RuleItem> {
  const { data } = await http.post<RuleItem>('/rules', payload)
  return data
}

export async function previewRule(template: string): Promise<{
  valid: boolean
  message: string
  missing: string[]
  rows: RulePreviewRow[]
  template: string
}> {
  const { data } = await http.post('/rules/preview', { template })
  return data
}

export async function activateRule(ruleId: string): Promise<RuleItem> {
  const { data } = await http.post<RuleItem>(`/rules/${ruleId}/activate`)
  return data
}
