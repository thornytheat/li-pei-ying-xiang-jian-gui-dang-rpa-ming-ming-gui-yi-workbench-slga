import http from './http'
import type { PendingQueue } from '../types/domain'

export async function fetchPendingQueue(): Promise<PendingQueue> {
  const { data } = await http.get<PendingQueue>('/pending')
  return data
}
