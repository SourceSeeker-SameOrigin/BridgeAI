import client from './client'
import type { PageResponse } from '../types/common'

export interface AuditLogItem {
  id: string
  tenant_id: string
  connector_id: string | null
  user_id: string | null
  agent_id: string | null
  log_type: string
  action: string
  request_payload: Record<string, unknown> | null
  response_payload: Record<string, unknown> | null
  status: string
  error_message: string | null
  duration_ms: number | null
  model_used: string | null
  tokens_in: number | null
  tokens_out: number | null
  created_at: string | null
}

export interface AuditLogFilters {
  log_type?: string
  status?: string
  start_date?: string
  end_date?: string
  action?: string
  user_id?: string
}

export async function getAuditLogs(
  page: number = 1,
  size: number = 20,
  filters: AuditLogFilters = {},
): Promise<PageResponse<AuditLogItem>> {
  const params: Record<string, unknown> = { page, size }
  if (filters.log_type) params.log_type = filters.log_type
  if (filters.status) params.status = filters.status
  if (filters.start_date) params.start_date = filters.start_date
  if (filters.end_date) params.end_date = filters.end_date
  if (filters.action) params.action = filters.action
  if (filters.user_id) params.user_id = filters.user_id

  const res = await client.get<PageResponse<AuditLogItem>>('/audit', { params })
  return res.data
}
