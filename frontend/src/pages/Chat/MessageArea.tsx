import { useRef, useEffect } from 'react'
import { Empty } from 'antd'
import { RobotOutlined } from '@ant-design/icons'
import type { Message } from '../../types/chat'
import MessageBubble from './MessageBubble'
import LoadingDots from '../../components/LoadingDots'

interface MessageAreaProps {
  messages: Message[]
  isStreaming: boolean
  onRate?: (messageId: string, rating: number) => void
}

export default function MessageArea({ messages, isStreaming, onRate }: MessageAreaProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isStreaming])

  if (messages.length === 0) {
    return (
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'column',
          gap: 16,
        }}
      >
        <div
          style={{
            width: 80,
            height: 80,
            borderRadius: 20,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 36,
          }}
          className="brand-gradient"
        >
          <RobotOutlined style={{ color: '#fff' }} />
        </div>
        <Empty
          description={
            <span style={{ color: '#64748b' }}>
              开始一段新的对话
            </span>
          }
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      </div>
    )
  }

  return (
    <div
      style={{
        flex: 1,
        overflow: 'auto',
        padding: '24px 16px',
      }}
    >
      <div style={{ maxWidth: 900, margin: '0 auto' }}>
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} onRate={onRate} />
        ))}
        {isStreaming && (
          <div style={{ paddingLeft: 56 }}>
            <LoadingDots />
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
