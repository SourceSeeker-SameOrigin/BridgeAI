import { Avatar } from 'antd'
import { UserOutlined, RobotOutlined } from '@ant-design/icons'
import type { Message } from '../../types/chat'
import MarkdownRenderer from '../../components/MarkdownRenderer'
import ToolCallCard from './ToolCallCard'
import RatingStars from './RatingStars'

interface MessageBubbleProps {
  message: Message
  onRate?: (messageId: string, rating: number) => void
}

export default function MessageBubble({ message, onRate }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  return (
    <div
      className="animate-slide-up"
      style={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        marginBottom: 20,
        gap: 12,
        paddingInline: 8,
      }}
    >
      {/* AI Avatar */}
      {!isUser && (
        <Avatar
          size={36}
          icon={<RobotOutlined />}
          style={{
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            flexShrink: 0,
            marginTop: 2,
          }}
        />
      )}

      {/* Message Content */}
      <div
        style={{
          maxWidth: '70%',
          minWidth: 80,
        }}
      >
        <div
          style={{
            padding: '12px 16px',
            borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
            background: isUser
              ? 'linear-gradient(135deg, #6366f1, #8b5cf6)'
              : 'rgba(17,24,39,0.7)',
            backdropFilter: isUser ? 'none' : 'blur(12px)',
            border: isUser ? 'none' : '1px solid rgba(148,163,184,0.1)',
            color: isUser ? '#fff' : '#e2e8f0',
            fontSize: 14,
            lineHeight: 1.6,
            boxShadow: isUser
              ? '0 4px 15px rgba(99,102,241,0.25)'
              : '0 2px 8px rgba(0,0,0,0.1)',
          }}
        >
          {isUser ? (
            <span style={{ whiteSpace: 'pre-wrap' }}>{message.content}</span>
          ) : (
            <>
              {message.toolCalls?.map((tc) => (
                <ToolCallCard key={tc.id} toolCall={tc} />
              ))}
              <MarkdownRenderer
                content={message.content}
                isStreaming={message.isStreaming}
              />
            </>
          )}
        </div>

        {/* Timestamp + Rating */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            marginTop: 4,
            paddingInline: 4,
            justifyContent: isUser ? 'flex-end' : 'flex-start',
          }}
        >
          <span style={{ fontSize: 11, color: '#475569' }}>
            {new Date(message.createdAt).toLocaleTimeString('zh-CN', {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </span>
          {!isUser && !message.isStreaming && (
            <RatingStars
              value={message.rating || 0}
              onChange={(rating) => onRate?.(message.id, rating)}
            />
          )}
        </div>
      </div>

      {/* User Avatar */}
      {isUser && (
        <Avatar
          size={36}
          icon={<UserOutlined />}
          style={{
            background: '#1e293b',
            border: '1px solid rgba(148,163,184,0.2)',
            flexShrink: 0,
            marginTop: 2,
          }}
        />
      )}
    </div>
  )
}
