import http from './http'
import type { MaterialType } from '../constants/enums'
import type { AttachmentItem } from '../types/domain'

export async function fetchAttachment(attachmentId: string): Promise<AttachmentItem> {
  const { data } = await http.get<AttachmentItem>(`/attachments/${attachmentId}`)
  return data
}

export async function confirmAttachment(
  attachmentId: string,
  payload: { material_type: MaterialType; policy_no?: string; note?: string },
): Promise<AttachmentItem> {
  const { data } = await http.post<AttachmentItem>(`/attachments/${attachmentId}/confirm`, payload)
  return data
}
