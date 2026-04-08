import { Input, Button, Empty } from 'antd'
import { PlusOutlined, SearchOutlined, DeleteOutlined, MessageOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import type { Conversation } from '../../types/chat'
import { useState, useMemo } from 'react'

interface SessionListProps {
  conversations: Conversation[]
  currentId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
}

function groupByDate(conversations: Conversation[], todayLabel: string, yesterdayLabel: string): Record<string, Conversation[]> {
  const groups: Record<string, Conversation[]> = {}
  const now = new Date()
  const today = now.toDateString()
  const yesterday = new Date(now.getTime() - 86400000).toDateString()

  for (const conv of conversations) {
    const d = new Date(conv.updatedAt).toDateString()
    let label: string
    if (d === today) label = todayLabel
    else if (d === yesterday) label = yesterdayLabel
    else label = new Date(conv.updatedAt).toLocaleDateString('zh-CN')

    if (!groups[label]) groups[label] = []
    groups[label].push(conv)
  }
  return groups
}

export default function SessionList({
  conversations,
  currentId,
  onSelect,
  onNew,
  onDelete,
}: SessionListProps) {
  const { t } = useTranslation()
  const [search, setSearch] = useState('')

  const filtered = useMemo(() => {
    if (!search) return conversations
    const q = search.toLowerCase()
    return conversations.filter(
      (c) =>
        c.title.toLowerCase().includes(q) ||
        c.lastMessage?.toLowerCase().includes(q),
    )
  }, [conversations, search])

  const grouped = useMemo(() => groupByDate(filtered, t('chat.today'), t('chat.yesterday')), [filtered, t])

  return (
    <div
      style={{
        width: 280,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        borderRight: '1px solid rgba(148,163,184,0.1)',
        background: 'rgba(17,24,39,0.4)',
      }}
    >
      {/* Header */}
      <div style={{ padding: '16px 12px 8px' }}>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          block
          onClick={onNew}
          style={{ marginBottom: 12, height: 38, borderRadius: 8 }}
        >
          {t('chat.newConversation')}
        </Button>
        <Input
          prefix={<SearchOutlined style={{ color: '#64748b' }} />}
          placeholder={t('chat.searchConversations')}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ borderRadius: 8 }}
          allowClear
        />
      </div>

      {/* Conversations */}
      <div style={{ flex: 1, overflow: 'auto', padding: '4px 8px' }}>
        {filtered.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={t('chat.noConversations')}
            style={{ marginTop: 60 }}
          />
        ) : (
          Object.entries(grouped).map(([label, convs]) => (
            <div key={label}>
              <div
                style={{
                  fontSize: 11,
                  color: '#64748b',
                  padding: '12px 8px 4px',
                  fontWeight: 500,
                }}
              >
                {label}
              </div>
              {convs.map((conv) => (
                <div
                  key={conv.id}
                  onClick={() => onSelect(conv.id)}
                  style={{
                    padding: '10px 12px',
                    borderRadius: 8,
                    cursor: 'pointer',
                    marginBottom: 2,
                    background:
                      conv.id === currentId
                        ? 'rgba(99,102,241,0.12)'
                        : 'transparent',
                    borderLeft:
                      conv.id === currentId
                        ? '2px solid #6366f1'
                        : '2px solid transparent',
                    transition: 'all 0.15s',
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 8,
                    position: 'relative',
                  }}
                >
                  <MessageOutlined style={{ color: '#64748b', marginTop: 3, flexShrink: 0 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: 500,
                        color: conv.id === currentId ? '#e2e8f0' : '#cbd5e1',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {conv.title}
                    </div>
                    {conv.lastMessage && (
                      <div
                        style={{
                          fontSize: 12,
                          color: '#64748b',
                          marginTop: 2,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {conv.lastMessage}
                      </div>
                    )}
                  </div>
                  <DeleteOutlined
                    onClick={(e) => {
                      e.stopPropagation()
                      onDelete(conv.id)
                    }}
                    style={{
                      color: '#475569',
                      fontSize: 12,
                      opacity: 0.5,
                      position: 'absolute',
                      right: 8,
                      top: 10,
                    }}
                  />
                </div>
              ))}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
