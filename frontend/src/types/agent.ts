export interface Agent {
  id: string
  name: string
  description: string
  avatar?: string
  model: string
  systemPrompt: string
  temperature: number
  maxTokens: number
  tools: string[]
  mcpConnectors: string[]
  knowledgeBases: string[]
  parentAgentId?: string
  status: 'active' | 'inactive' | 'draft'
  createdAt: string
  updatedAt: string
}

export interface AgentCreate {
  name: string
  description: string
  model: string
  systemPrompt: string
  temperature?: number
  maxTokens?: number
  tools?: string[]
  mcpConnectors?: string[]
  knowledgeBases?: string[]
  knowledgeBaseId?: string
  parentAgentId?: string
}

export interface AgentUpdate extends Partial<AgentCreate> {
  id: string
  status?: 'active' | 'inactive' | 'draft'
  knowledgeBaseId?: string
}
