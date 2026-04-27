import client from './client'
import type { PageResponse } from '../types/common'
import type { Agent, AgentCreate, AgentUpdate } from '../types/agent'

/** Agent template returned by GET /agents/templates */
export interface AgentTemplate {
  key: string
  name: string
  description: string
  system_prompt: string
  model_config?: {
    model_provider?: string
    model_name?: string
    temperature?: number
    max_tokens?: number
  }
}

export async function getAgentTemplates(): Promise<AgentTemplate[]> {
  const res = await client.get<AgentTemplate[]>('/agents/templates')
  return res.data || []
}

/** Backend AgentResponse shape */
interface BackendAgent {
  id: string
  name: string
  description?: string
  parent_agent_id?: string
  task_key?: string
  system_prompt?: string
  knowledge_base_id?: string
  model_config_data?: Record<string, unknown>
  tools?: unknown[]
  is_active: boolean
  version: number
  created_at: string
  updated_at: string
}

/** Map backend response to frontend Agent type */
function mapAgent(b: BackendAgent): Agent {
  const cfg = b.model_config_data || {}
  return {
    id: b.id,
    name: b.name,
    description: b.description || '',
    model: (cfg.model_name as string) || (cfg.model as string) || 'unknown',
    systemPrompt: b.system_prompt || '',
    temperature: (cfg.temperature as number) ?? 0.7,
    maxTokens: (cfg.max_tokens as number) ?? 4096,
    tools: (b.tools as string[]) || [],
    plugins: (cfg.allowed_plugins as string[]) || [],
    knowledgeBaseId: b.knowledge_base_id,
    parentAgentId: b.parent_agent_id,
    status: b.is_active ? 'active' : 'inactive',
    createdAt: b.created_at,
    updatedAt: b.updated_at,
  }
}

export async function getAgents(page = 1, size = 50): Promise<Agent[]> {
  const res = await client.get<PageResponse<BackendAgent>>('/agents', {
    params: { page, size },
  })
  return (res.data.items || []).map(mapAgent)
}

export async function getAgent(id: string): Promise<Agent> {
  const res = await client.get<BackendAgent>(`/agents/${id}`)
  return mapAgent(res.data)
}

export async function createAgent(data: AgentCreate): Promise<Agent> {
  const modelConfig: Record<string, unknown> = {
    model_name: data.model,
    temperature: data.temperature ?? 0.7,
    max_tokens: data.maxTokens ?? 4096,
  }
  if (data.plugins !== undefined) modelConfig.allowed_plugins = data.plugins
  const payload: Record<string, unknown> = {
    name: data.name,
    description: data.description,
    system_prompt: data.systemPrompt,
    model_config_data: modelConfig,
    tools: data.tools || [],
  }
  if (data.knowledgeBaseId) payload.knowledge_base_id = data.knowledgeBaseId
  if (data.parentAgentId) payload.parent_agent_id = data.parentAgentId
  const res = await client.post<BackendAgent>('/agents', payload)
  return mapAgent(res.data)
}

export async function updateAgent(data: AgentUpdate): Promise<Agent> {
  const { id, ...rest } = data
  const payload: Record<string, unknown> = {}
  if (rest.name !== undefined) payload.name = rest.name
  if (rest.description !== undefined) payload.description = rest.description
  if (rest.systemPrompt !== undefined) payload.system_prompt = rest.systemPrompt

  // model_config_data is JSONB-merged on the backend, so we only need to send the
  // keys we actually want to change. Sending all four every time would still work
  // (merge is upsert), but only including changed keys is cleaner and avoids
  // accidentally pinning a default value the user never touched.
  const cfgPatch: Record<string, unknown> = {}
  if (rest.model !== undefined) cfgPatch.model_name = rest.model
  if (rest.temperature !== undefined) cfgPatch.temperature = rest.temperature
  if (rest.maxTokens !== undefined) cfgPatch.max_tokens = rest.maxTokens
  if (rest.plugins !== undefined) cfgPatch.allowed_plugins = rest.plugins
  if (Object.keys(cfgPatch).length > 0) payload.model_config_data = cfgPatch

  if (rest.tools !== undefined) payload.tools = rest.tools
  if (rest.knowledgeBaseId !== undefined) payload.knowledge_base_id = rest.knowledgeBaseId || null
  if (rest.parentAgentId !== undefined) payload.parent_agent_id = rest.parentAgentId || null
  if (rest.status !== undefined) payload.is_active = rest.status === 'active'

  const res = await client.put<BackendAgent>(`/agents/${id}`, payload)
  return mapAgent(res.data)
}

export async function deleteAgent(id: string): Promise<void> {
  await client.delete(`/agents/${id}`)
}
