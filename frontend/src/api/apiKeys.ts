import client from './client'
import type { PageResponse } from '../types/common'

export interface ApiKeyItem {
  id: string
  name: string
  prefix: string
  scopes: string[]
  is_active: boolean
  created_at: string
  expires_at: string | null
  last_used_at: string | null
}

export interface ApiKeyCreated {
  id: string
  name: string
  key: string
  prefix: string
  scopes: string[]
  is_active: boolean
  created_at: string
  expires_at: string | null
}

export async function getApiKeys(page = 1, size = 50): Promise<ApiKeyItem[]> {
  const res = await client.get<PageResponse<ApiKeyItem>>('/api-keys', {
    params: { page, size },
  })
  return res.data.items || []
}

export async function createApiKey(
  data: { name: string; scopes?: string[] },
): Promise<ApiKeyCreated> {
  const res = await client.post<ApiKeyCreated>('/api-keys', data)
  return res.data
}

export async function revokeApiKey(id: string): Promise<void> {
  await client.post(`/api-keys/${id}/revoke`)
}

export async function deleteApiKey(id: string): Promise<void> {
  await client.delete(`/api-keys/${id}`)
}
