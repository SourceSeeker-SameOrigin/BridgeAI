import client from './client'
import type { PageResponse } from '../types/common'
import type { McpConnector } from '../types/chat'

/** Backend connector response shape */
interface BackendConnector {
  id: string
  name: string
  description?: string
  connector_type: string
  endpoint_url: string
  is_active: boolean
  created_at: string
  updated_at: string
}

/** Map backend connector to frontend McpConnector type */
function mapConnector(b: BackendConnector): McpConnector {
  return {
    id: b.id,
    name: b.name,
    description: b.description || '',
    type: b.connector_type as McpConnector['type'],
    endpoint: b.endpoint_url,
    status: b.is_active ? 'connected' : 'disconnected',
    tools: [],
    createdAt: b.created_at,
  }
}

export async function getMcpConnectors(page = 1, size = 50): Promise<McpConnector[]> {
  const res = await client.get<PageResponse<BackendConnector>>('/mcp', {
    params: { page, size },
  })
  return (res.data.items || []).map(mapConnector)
}

export async function getMcpConnector(id: string): Promise<McpConnector> {
  const res = await client.get<BackendConnector>(`/mcp/${id}`)
  return mapConnector(res.data)
}

export async function createMcpConnector(
  data: { name: string; description: string; type: string; endpoint: string; config?: Record<string, unknown> },
): Promise<McpConnector> {
  const payload: Record<string, unknown> = {
    name: data.name,
    description: data.description,
    connector_type: data.type,
    endpoint_url: data.endpoint,
  }
  if (data.config) {
    payload.config = data.config
  }
  const res = await client.post<BackendConnector>('/mcp', payload)
  return mapConnector(res.data)
}

export async function updateMcpConnector(
  id: string,
  data: Partial<{ name: string; description: string; type: string; endpoint: string }>,
): Promise<McpConnector> {
  const payload: Record<string, unknown> = {}
  if (data.name !== undefined) payload.name = data.name
  if (data.description !== undefined) payload.description = data.description
  if (data.type !== undefined) payload.connector_type = data.type
  if (data.endpoint !== undefined) payload.endpoint_url = data.endpoint
  const res = await client.put<BackendConnector>(`/mcp/${id}`, payload)
  return mapConnector(res.data)
}

export async function deleteMcpConnector(id: string): Promise<void> {
  await client.delete(`/mcp/${id}`)
}

export interface McpToolInfo {
  name: string
  description: string
  input_schema?: Record<string, unknown>
}

export async function getMcpConnectorTools(id: string): Promise<McpToolInfo[]> {
  try {
    const res = await client.get<McpToolInfo[]>(`/mcp/${id}/tools`)
    return res.data || []
  } catch {
    return []
  }
}

export async function testMcpConnector(
  id: string,
): Promise<{ success: boolean; message: string }> {
  try {
    const res = await client.post<{ healthy?: boolean; success?: boolean; message?: string }>(
      `/mcp/${id}/test`,
    )
    // Backend returns {healthy: true}, map to {success, message}
    const healthy = res.data.healthy ?? res.data.success ?? false
    return { success: healthy, message: healthy ? '连接成功' : '连接失败' }
  } catch (err) {
    return {
      success: false,
      message: err instanceof Error ? err.message : '测试失败',
    }
  }
}
