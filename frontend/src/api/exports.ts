import http from './http'
import { downloadBlob } from '../utils/format'

async function getBlob(path: string): Promise<{ filename: string; blob: Blob }> {
  const response = await http.get(path, { responseType: 'blob' })
  const disposition: string = response.headers['content-disposition'] ?? ''
  const match = disposition.match(/filename="?([^";]+)"?/)
  const filename = match ? match[1] : path.split('/').pop() ?? 'export.csv'
  return { filename, blob: response.data as Blob }
}

export async function downloadHandover(): Promise<string> {
  const { filename, blob } = await getBlob('/export/handover.csv')
  downloadBlob(filename, blob)
  return filename
}

export async function downloadAudit(): Promise<string> {
  const { filename, blob } = await getBlob('/export/audit.csv')
  downloadBlob(filename, blob)
  return filename
}
