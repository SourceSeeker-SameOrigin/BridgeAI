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
  return {
    id: b.id,
    name: b.name,
    description: b.description || '',
    model: (b.model_config_data?.model as string) || (b.model_config_data?.model_name as string) || 'unknown',
    systemPrompt: b.system_prompt || '',
    temperature: (b.model_config_data?.temperature as number) ?? 0.7,
    maxTokens: (b.model_config_data?.max_tokens as number) ?? 4096,
    tools: (b.tools as string[]) || [],
    mcpConnectors: [],
    knowledgeBases: b.knowledge_base_id ? [b.knowledge_base_id] : [],
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
  const payload: Record<string, unknown> = {
    name: data.name,
    description: data.description,
    system_prompt: data.systemPrompt,
    model_config_data: {
      model: data.model,
      temperature: data.temperature ?? 0.7,
      max_tokens: data.maxTokens ?? 4096,
    },
    tools: data.tools || [],
  }
  if (data.knowledgeBaseId) {
    payload.knowledge_base_id = data.knowledgeBaseId
  }
  const res = await client.post<BackendAgent>('/agents', payload)
  return mapAgent(res.data)
}

export async function updateAgent(data: AgentUpdate): Promise<Agent> {
  const { id, ...rest } = data
  const payload: Record<string, unknown> = {}
  if (rest.name !== undefined) payload.name = rest.name
  if (rest.description !== undefined) payload.description = rest.description
  if (rest.systemPrompt !== undefined) payload.system_prompt = rest.systemPrompt
  if (rest.model !== undefined || rest.temperature !== undefined || rest.maxTokens !== undefined) {
    payload.model_config_data = {
      model: rest.model,
      temperature: rest.temperature ?? 0.7,
      max_tokens: rest.maxTokens ?? 4096,
    }
  }
  if (rest.tools !== undefined) payload.tools = rest.tools
  if (rest.knowledgeBaseId !== undefined) payload.knowledge_base_id = rest.knowledgeBaseId || null
  if (rest.status !== undefined) payload.is_active = rest.status === 'active'

  const res = await client.put<BackendAgent>(`/agents/${id}`, payload)
  return mapAgent(res.data)
}

export async function deleteAgent(id: string): Promise<void> {
  await client.delete(`/agents/${id}`)
}
