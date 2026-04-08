import { useState } from 'react'
import { CaretRightOutlined, CheckCircleOutlined, LoadingOutlined, CloseCircleOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import type { ToolCall } from '../../types/chat'

interface ToolCallCardProps {
  toolCall: ToolCall
}

const statusIcons: Record<string, React.ReactNode> = {
  running: <LoadingOutlined spin style={{ color: '#3b82f6' }} />,
  success: <CheckCircleOutlined style={{ color: '#22c55e' }} />,
  error: <CloseCircleOutlined style={{ color: '#ef4444' }} />,
}

export default function ToolCallCard({ toolCall }: ToolCallCardProps) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)

  return (
    <div
      style={{
        background: 'rgba(26,35,50,0.6)',
        border: '1px solid rgba(148,163,184,0.1)',
        borderRadius: 8,
        marginBlock: 8,
        overflow: 'hidden',
      }}
    >
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '8px 12px',
          cursor: 'pointer',
          fontSize: 13,
        }}
      >
        <CaretRightOutlined
          style={{
            transform: expanded ? 'rotate(90deg)' : 'rotate(0)',
            transition: 'transform 0.2s',
            color: '#64748b',
            fontSize: 10,
          }}
        />
        {statusIcons[toolCall.status]}
        <span style={{ color: '#a78bfa', fontWeight: 500 }}>{toolCall.name}</span>
        {toolCall.duration != null && (
          <span style={{ color: '#64748b', fontSize: 11, marginLeft: 'auto' }}>
            {toolCall.duration}ms
          </span>
        )}
      </div>
      {expanded && (
        <div style={{ padding: '0 12px 12px', fontSize: 12, color: '#94a3b8' }}>
          <div style={{ marginBottom: 6, fontWeight: 500, color: '#cbd5e1' }}>{t('chat.toolCallParams')}</div>
          <pre
            style={{
              background: 'rgba(0,0,0,0.2)',
              padding: 8,
              borderRadius: 4,
              overflow: 'auto',
              maxHeight: 120,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all',
            }}
          >
            {toolCall.arguments}
          </pre>
          {toolCall.result && (
            <>
              <div style={{ marginBottom: 6, marginTop: 8, fontWeight: 500, color: '#cbd5e1' }}>{t('chat.toolCallResult')}</div>
              <pre
                style={{
                  background: 'rgba(0,0,0,0.2)',
                  padding: 8,
                  borderRadius: 4,
                  overflow: 'auto',
                  maxHeight: 120,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-all',
                }}
              >
                {toolCall.result}
              </pre>
            </>
          )}
        </div>
      )}
    </div>
  )
}
