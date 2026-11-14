export interface ApiError {
  code: string
  message: string
  detail?: string
  traceId?: string | null
  status?: number
}
