export interface Conversation {
  id: string
  title: string
  agentId: string
  agentName: string
  lastMessage?: string
  messageCount: number
  createdAt: string
  updatedAt: string
}

export interface ToolCall {
  id: string
  name: string
  arguments: string
  result?: string
  status: 'running' | 'success' | 'error'
  duration?: number
}

export interface Message {
  id: string
  conversationId: string
  role: 'user' | 'assistant' | 'system'
  content: string
  toolCalls?: ToolCall[]
  rating?: number
  createdAt: string
  isStreaming?: boolean
}

export interface ChatRequest {
  conversationId?: string
  agentId: string
  message: string
  files?: string[]
}

export interface McpConnector {
  id: string
  name: string
  description: string
  type: 'database' | 'feishu' | 'http_api' | 'stdio' | 'sse' | 'streamable_http'
  endpoint: string
  status: 'connected' | 'disconnected' | 'error'
  tools: McpTool[]
  createdAt: string
}

export interface McpTool {
  name: string
  description: string
  inputSchema: Record<string, unknown>
}

export interface KnowledgeBase {
  id: string
  name: string
  description: string
  documentCount: number
  totalSize: string
  status: 'ready' | 'indexing' | 'error'
  createdAt: string
  updatedAt: string
}

export interface KnowledgeDocument {
  id: string
  name: string
  type: string
  size: string
  status: 'indexed' | 'indexing' | 'failed'
  createdAt: string
}
