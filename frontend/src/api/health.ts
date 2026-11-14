import http from './http'

export interface HealthPayload {
  status: string
  brand: string
  database: boolean
  redis: boolean
  archive_files: number
  version: string
}

export async function fetchHealth(): Promise<HealthPayload> {
  const { data } = await http.get<HealthPayload>('/health')
  return data
}
