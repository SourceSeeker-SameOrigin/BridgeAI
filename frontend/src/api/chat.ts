import client from './client'
import type { PageResponse } from '../types/common'
import type { Conversation, Message } from '../types/chat'

export async function getConversations(
  page = 1,
  size = 20,
): Promise<PageResponse<Conversation>> {
  const res = await client.get<PageResponse<Conversation>>(
    '/chat/conversations',
    { params: { page, size } },
  )
  return res.data
}

export async function getMessages(
  conversationId: string,
  page = 1,
  size = 50,
): Promise<PageResponse<Message>> {
  const res = await client.get<PageResponse<Message>>(
    `/chat/conversations/${conversationId}/messages`,
    { params: { page, size } },
  )
  return res.data
}

export async function deleteConversation(id: string): Promise<void> {
  await client.delete(`/chat/conversations/${id}`)
}

export async function rateMessage(
  messageId: string,
  rating: number,
  feedback?: string,
): Promise<void> {
  await client.post(`/chat/messages/${messageId}/rate`, { rating, feedback })
}

/**
 * Send message via SSE stream.
 * Backend expects: { agent_id?, messages: [{role, content}], stream: true }
 * Returns an AbortController so callers can cancel.
 */
export function sendMessageSSE(
  request: {
    agentId?: string
    conversationId?: string
    message: string
    history?: Array<{ role: string; content: string }>
  },
  onChunk: (chunk: string) => void,
  onToolCall?: (toolCall: { id: string; name: string; status: string }) => void,
  onAnalysis?: (analysis: string) => void,
  onDone?: (conversationId: string) => void,
  onError?: (error: string) => void,
  onMeta?: (meta: { conversationId: string; responseId: string }) => void,
): AbortController {
  const controller = new AbortController()
  const token = localStorage.getItem('token')

  // Build messages array for backend
  const messages = [
    ...(request.history || []),
    { role: 'user', content: request.message },
  ]

  fetch('/api/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      agent_id: request.agentId || undefined,
      conversation_id: request.conversationId || undefined,
      messages,
      stream: true,
    }),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const text = await response.text().catch(() => '')
        onError?.(`请求失败: ${response.status} ${text}`)
        return
      }

      const reader = response.body?.getReader()
      if (!reader) return

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim()
            if (data === '[DONE]') {
              onDone?.('')
              return
            }
            try {
              const parsed = JSON.parse(data)
              if (parsed.type === 'meta') {
                onMeta?.({
                  conversationId: parsed.conversation_id || '',
                  responseId: parsed.response_id || '',
                })
              } else if (parsed.type === 'content') {
                onChunk(parsed.content || '')
              } else if (parsed.type === 'tool_call') {
                onToolCall?.(parsed)
              } else if (parsed.type === 'analysis') {
                onAnalysis?.(parsed.content || '')
              } else if (parsed.type === 'done') {
                onDone?.(parsed.conversation_id || parsed.conversationId || '')
              } else if (parsed.type === 'error') {
                onError?.(parsed.message || parsed.content || '未知错误')
              }
            } catch {
              // Treat as plain text content
              if (data) onChunk(data)
            }
          }
        }
      }
      // Stream ended without explicit done event
      onDone?.('')
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        onError?.(err.message)
      }
    })

  return controller
}
