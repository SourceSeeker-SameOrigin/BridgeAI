interface StatusBadgeProps {
  status: 'active' | 'inactive' | 'connected' | 'disconnected' | 'error' | 'ready' | 'indexing' | 'success' | 'running' | 'draft'
  label?: string
}

const STATUS_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
  active: { color: '#22c55e', bg: 'rgba(34,197,94,0.1)', label: '运行中' },
  connected: { color: '#22c55e', bg: 'rgba(34,197,94,0.1)', label: '已连接' },
  ready: { color: '#22c55e', bg: 'rgba(34,197,94,0.1)', label: '就绪' },
  success: { color: '#22c55e', bg: 'rgba(34,197,94,0.1)', label: '成功' },
  running: { color: '#3b82f6', bg: 'rgba(59,130,246,0.1)', label: '运行中' },
  indexing: { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)', label: '索引中' },
  draft: { color: '#94a3b8', bg: 'rgba(148,163,184,0.1)', label: '草稿' },
  inactive: { color: '#94a3b8', bg: 'rgba(148,163,184,0.1)', label: '未激活' },
  disconnected: { color: '#ef4444', bg: 'rgba(239,68,68,0.1)', label: '已断开' },
  error: { color: '#ef4444', bg: 'rgba(239,68,68,0.1)', label: '错误' },
}

export default function StatusBadge({ status, label }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.inactive
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '2px 10px',
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 500,
        color: config.color,
        background: config.bg,
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          background: config.color,
          boxShadow: `0 0 6px ${config.color}`,
        }}
      />
      {label || config.label}
    </span>
  )
}
