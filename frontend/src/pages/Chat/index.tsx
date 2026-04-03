import { useState, useCallback, useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Select, Tag, Spin, message, Modal } from 'antd'
import { RobotOutlined, InfoCircleOutlined, LoadingOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import type { Conversation, Message } from '../../types/chat'
import type { Agent } from '../../types/agent'
import { getAgents } from '../../api/agents'
import { sendMessageSSE, rateMessage, getConversations, getMessages, deleteConversation as apiDeleteConversation } from '../../api/chat'
import SessionList from './SessionList'
import MessageArea from './MessageArea'
import InputBar from './InputBar'

let msgIdCounter = 100

export default function ChatPage() {
  const { t } = useTranslation()
  const [searchParams] = useSearchParams()
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [currentId, setCurrentId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [agents, setAgents] = useState<Agent[]>([])
  const [selectedAgent, setSelectedAgent] = useState<string>('')
  const [showContext, setShowContext] = useState(true)
  const [agentsLoading, setAgentsLoading] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  // Track backend-assigned conversationId for the current conversation
  const realConvIdRef = useRef<Record<string, string>>({})

  const currentConv = conversations.find((c) => c.id === currentId)
  const currentMessages = messages.filter(
    (m) => m.conversationId === currentId,
  )

  // Load agents from API
  useEffect(() => {
    let cancelled = false
    setAgentsLoading(true)
    const agentIdFromUrl = searchParams.get('agentId')
    getAgents()
      .then((data) => {
        if (cancelled) return
        setAgents(data)
        if (agentIdFromUrl && data.some((a) => a.id === agentIdFromUrl)) {
          setSelectedAgent(agentIdFromUrl)
        } else if (data.length > 0 && !selectedAgent) {
          setSelectedAgent(data[0].id)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          message.error(`${t('chat.loadAgentsFailed')}: ${err.message}`)
        }
      })
      .finally(() => {
        if (!cancelled) setAgentsLoading(false)
      })
    return () => { cancelled = true }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Load existing conversations from backend on mount
  useEffect(() => {
    let cancelled = false
    getConversations()
      .then((data) => {
        if (cancelled || !data.items || data.items.length === 0) return
        setConversations(data.items)
      })
      .catch(() => {
        // silently ignore — empty conversation list is fine
      })
    return () => { cancelled = true }
  }, [])

  const handleSelectConversation = useCallback((id: string) => {
    setCurrentId(id)
    // Load messages from backend if they aren't already in state
    const existingMsgs = messages.filter((m) => m.conversationId === id)
    if (existingMsgs.length === 0) {
      getMessages(id)
        .then((data) => {
          if (data.items && data.items.length > 0) {
            setMessages((prev) => [
              ...prev,
              ...data.items.filter((m) => !prev.some((p) => p.id === m.id)),
            ])
          }
        })
        .catch(() => { /* silently ignore */ })
    }
  }, [messages])

  const handleNewConversation = useCallback(() => {
    const id = `conv-${Date.now()}`
    const agent = agents.find((a) => a.id === selectedAgent)
    const newConv: Conversation = {
      id,
      title: t('chat.newConversationTitle'),
      agentId: selectedAgent,
      agentName: agent?.name || 'Assistant',
      messageCount: 0,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
    setConversations((prev) => [newConv, ...prev])
    setCurrentId(id)
  }, [selectedAgent, agents])

  const handleDeleteConversation = useCallback(
    (id: string) => {
      Modal.confirm({
        title: t('common.confirmDelete'),
        content: t('chat.confirmDeleteConversation'),
        okType: 'danger',
        okText: t('common.delete'),
        cancelText: t('common.cancel'),
        onOk: () => {
          setConversations((prev) => prev.filter((c) => c.id !== id))
          setMessages((prev) => prev.filter((m) => m.conversationId !== id))
          if (currentId === id) setCurrentId(null)
          // Also delete from backend (fire and forget)
          apiDeleteConversation(id).catch(() => { /* ignore errors for local-only convs */ })
        },
      })
    },
    [currentId],
  )

  const handleSend = useCallback(
    (content: string) => {
      let convId = currentId
      // Auto-create conversation if none selected
      if (!convId) {
        convId = `conv-${Date.now()}`
        const agent = agents.find((a) => a.id === selectedAgent)
        const newConv: Conversation = {
          id: convId,
          title: content.slice(0, 30) || t('chat.newConversationTitle'),
          agentId: selectedAgent,
          agentName: agent?.name || 'Assistant',
          messageCount: 0,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        }
        setConversations((prev) => [newConv, ...prev])
        setCurrentId(convId)
      }

      const targetConvId = convId

      // Add user message
      const userMsg: Message = {
        id: `msg-${++msgIdCounter}`,
        conversationId: targetConvId,
        role: 'user',
        content,
        createdAt: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, userMsg])

      // Build history from existing messages for this conversation (include the new user message)
      const history = [
        ...messages
          .filter((m) => m.conversationId === targetConvId)
          .map((m) => ({ role: m.role, content: m.content })),
        { role: 'user', content },
      ]

      // Create assistant placeholder
      const aiMsgId = `msg-${++msgIdCounter}`
      const aiMsg: Message = {
        id: aiMsgId,
        conversationId: targetConvId,
        role: 'assistant',
        content: '',
        isStreaming: true,
        createdAt: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, aiMsg])
      setIsStreaming(true)

      // Track the real backend message ID (updated when meta event arrives)
      let realMsgId = aiMsgId

      // Resolve the real backend conversationId (if we have one from a previous meta event)
      const backendConvId = realConvIdRef.current[targetConvId] || undefined

      // Send SSE request
      const controller = sendMessageSSE(
        {
          agentId: selectedAgent || undefined,
          conversationId: backendConvId,
          message: content,
          history,
        },
        // onChunk — filter out any leaked <analysis>...</analysis> tags
        (chunk) => {
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== realMsgId) return m
              let newContent = m.content + chunk
              // Strip <analysis>...</analysis> blocks (including partial)
              newContent = newContent.replace(/<analysis>[\s\S]*?<\/analysis>/g, '')
              // Strip unclosed <analysis> at the end (still streaming)
              newContent = newContent.replace(/<analysis>[\s\S]*$/, '')
              return { ...m, content: newContent }
            }),
          )
        },
        // onToolCall
        (toolCall) => {
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== realMsgId) return m
              const existing = m.toolCalls || []
              const idx = existing.findIndex((t) => t.id === toolCall.id)
              if (idx >= 0) {
                const updated = [...existing]
                updated[idx] = {
                  ...updated[idx],
                  name: toolCall.name,
                  status: toolCall.status as 'running' | 'success' | 'error',
                }
                return { ...m, toolCalls: updated }
              }
              return {
                ...m,
                toolCalls: [
                  ...existing,
                  {
                    id: toolCall.id,
                    name: toolCall.name,
                    arguments: '',
                    status: toolCall.status as 'running' | 'success' | 'error',
                  },
                ],
              }
            }),
          )
        },
        // onAnalysis - ignored for now
        undefined,
        // onDone
        () => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === realMsgId ? { ...m, isStreaming: false } : m,
            ),
          )
          setIsStreaming(false)
          abortRef.current = null
        },
        // onError
        (error) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === realMsgId
                ? { ...m, content: m.content || `${t('chat.errorPrefix')} ${error}`, isStreaming: false }
                : m,
            ),
          )
          setIsStreaming(false)
          abortRef.current = null
          message.error(error)
        },
        // onMeta — update the AI message ID with the real backend response_id
        (meta) => {
          if (meta.responseId) {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === realMsgId ? { ...m, id: meta.responseId } : m,
              ),
            )
            realMsgId = meta.responseId
          }
          if (meta.conversationId) {
            // Track the backend-assigned conversationId for subsequent messages
            realConvIdRef.current[targetConvId] = meta.conversationId
            realConvIdRef.current[meta.conversationId] = meta.conversationId
            // Update conversation ID if backend assigned one
            setConversations((prev) =>
              prev.map((c) =>
                c.id === targetConvId ? { ...c, id: meta.conversationId } : c,
              ),
            )
            setMessages((prev) =>
              prev.map((m) =>
                m.conversationId === targetConvId
                  ? { ...m, conversationId: meta.conversationId }
                  : m,
              ),
            )
            if (currentId === targetConvId || !currentId) {
              setCurrentId(meta.conversationId)
            }
          }
        },
      )

      abortRef.current = controller

      // Update conversation title with first message
      setConversations((prev) =>
        prev.map((c) =>
          c.id === targetConvId
            ? {
                ...c,
                title: c.messageCount === 0 ? content.slice(0, 30) : c.title,
                lastMessage: content,
                messageCount: c.messageCount + 1,
                updatedAt: new Date().toISOString(),
              }
            : c,
        ),
      )
    },
    [currentId, selectedAgent, agents, messages],
  )

  const handleRate = useCallback((messageId: string, rating: number) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === messageId ? { ...m, rating } : m)),
    )
    rateMessage(messageId, rating).catch((err) => {
      message.error(`${t('chat.rateFailed')}: ${err.message}`)
    })
  }, [])

  const currentAgent = agents.find((a) => a.id === (currentConv?.agentId || selectedAgent))

  return (
    <div
      style={{
        height: 'calc(100vh - 64px - 48px)',
        display: 'flex',
        borderRadius: 12,
        overflow: 'hidden',
        border: '1px solid rgba(148,163,184,0.1)',
        background: 'rgba(17,24,39,0.3)',
      }}
    >
      {/* Left: Session List */}
      <SessionList
        conversations={conversations}
        currentId={currentId}
        onSelect={handleSelectConversation}
        onNew={handleNewConversation}
        onDelete={handleDeleteConversation}
      />

      {/* Center: Messages */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Agent Selector Bar */}
        <div
          style={{
            padding: '10px 16px',
            borderBottom: '1px solid rgba(148,163,184,0.1)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'rgba(17,24,39,0.5)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {agentsLoading ? (
              <Spin indicator={<LoadingOutlined style={{ fontSize: 16, color: '#6366f1' }} />} />
            ) : (
              <Select
                value={selectedAgent || undefined}
                onChange={setSelectedAgent}
                placeholder={t('chat.selectAgent')}
                style={{ width: 180 }}
                options={agents.map((a) => ({
                  label: a.name,
                  value: a.id,
                }))}
                suffixIcon={<RobotOutlined style={{ color: '#6366f1' }} />}
              />
            )}
            {currentConv && (
              <Tag color="processing" style={{ borderRadius: 4 }}>
                {currentConv.agentName}
              </Tag>
            )}
          </div>
          <InfoCircleOutlined
            onClick={() => setShowContext(!showContext)}
            style={{
              fontSize: 16,
              cursor: 'pointer',
              color: showContext ? '#6366f1' : '#64748b',
            }}
          />
        </div>

        <MessageArea
          messages={currentMessages}
          isStreaming={isStreaming}
          onRate={handleRate}
        />

        <InputBar onSend={handleSend} disabled={isStreaming} />
      </div>

      {/* Right: Context Panel */}
      {showContext && (
        <div
          style={{
            width: 260,
            borderLeft: '1px solid rgba(148,163,184,0.1)',
            background: 'rgba(17,24,39,0.4)',
            padding: 16,
            overflow: 'auto',
          }}
        >
          <h4 style={{ color: '#e2e8f0', fontSize: 13, marginBottom: 16, fontWeight: 600 }}>
            {t('chat.conversationInfo')}
          </h4>

          {currentConv ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>{t('chat.agent')}</div>
                <div style={{ fontSize: 13, color: '#cbd5e1' }}>{currentConv.agentName}</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>{t('chat.messageCount')}</div>
                <div style={{ fontSize: 13, color: '#cbd5e1' }}>{currentMessages.length}</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>{t('chat.createdAt')}</div>
                <div style={{ fontSize: 13, color: '#cbd5e1' }}>
                  {new Date(currentConv.createdAt).toLocaleString('zh-CN')}
                </div>
              </div>

              {currentAgent && (
                <>
                  <div style={{ borderTop: '1px solid rgba(148,163,184,0.1)', paddingTop: 16 }}>
                    <div style={{ fontSize: 11, color: '#64748b', marginBottom: 8 }}>{t('common.tools')}</div>
                    {(currentAgent.tools || []).length > 0 ? (
                      currentAgent.tools.map((tool) => (
                        <Tag
                          key={String(tool)}
                          style={{
                            marginBottom: 4,
                            background: 'rgba(99,102,241,0.1)',
                            borderColor: 'rgba(99,102,241,0.2)',
                            color: '#a78bfa',
                            borderRadius: 4,
                          }}
                        >
                          {String(tool)}
                        </Tag>
                      ))
                    ) : (
                      <span style={{ fontSize: 12, color: '#64748b' }}>{t('chat.noTools')}</span>
                    )}
                  </div>

                  <div style={{ borderTop: '1px solid rgba(148,163,184,0.1)', paddingTop: 16 }}>
                    <div style={{ fontSize: 11, color: '#64748b', marginBottom: 8 }}>{t('chat.modelInfo')}</div>
                    <div style={{ fontSize: 12, color: '#94a3b8' }}>
                      {currentAgent.model}
                    </div>
                    <div style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>
                      Temperature: {currentAgent.temperature}
                    </div>
                    <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>
                      Max Tokens: {currentAgent.maxTokens}
                    </div>
                  </div>
                </>
              )}
            </div>
          ) : (
            <div style={{ color: '#64748b', fontSize: 13 }}>{t('chat.selectConversationToView')}</div>
          )}
        </div>
      )}
    </div>
  )
}
