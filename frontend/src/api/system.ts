import client from './client'

export interface SystemModel {
  id: string
  name: string
  provider: string
  available: boolean
}

export async function getSystemModels(): Promise<SystemModel[]> {
  const res = await client.get<SystemModel[]>('/system/models')
  return res.data
}

export interface SystemHealth {
  status: string
  database: string
  redis: string
  minio: string
}

export async function getSystemHealth(): Promise<SystemHealth> {
  const res = await client.get<SystemHealth>('/system/health')
  return res.data
}

export interface SystemSettings {
  default_model?: string
  default_temperature?: number
  stream_enabled?: boolean
  content_filter_enabled?: boolean
  platform_name?: string
  language?: string
  notifications_enabled?: boolean
  audit_log_enabled?: boolean
}

export async function getSystemSettings(): Promise<SystemSettings> {
  const res = await client.get<SystemSettings>('/system/settings')
  return res.data
}

export async function updateSystemSettings(data: SystemSettings): Promise<SystemSettings> {
  const res = await client.put<SystemSettings>('/system/settings', data)
  return res.data
}

export interface DailyUsage {
  date: string
  messages: number
  tokens: number
}

export interface DistributionItem {
  intent?: string
  emotion?: string
  model?: string
  count: number
}

export interface SystemStats {
  total_conversations: number
  total_messages: number
  total_agents: number
  total_mcp_connectors: number
  total_knowledge_bases: number
  total_documents: number
  daily_usage: DailyUsage[]
  intent_distribution: DistributionItem[]
  emotion_distribution: DistributionItem[]
  model_usage: DistributionItem[]
}

export async function getSystemStats(): Promise<SystemStats> {
  const res = await client.get<SystemStats>('/system/stats')
  return res.data
}
