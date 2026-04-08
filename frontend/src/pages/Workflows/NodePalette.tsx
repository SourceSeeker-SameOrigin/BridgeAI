import { memo } from 'react'
import { NODE_PALETTE } from './nodeTypes'

/** Sidebar palette for dragging nodes onto the canvas */
function NodePalette() {
  const onDragStart = (event: React.DragEvent, nodeType: string) => {
    event.dataTransfer.setData('application/reactflow-nodetype', nodeType)
    event.dataTransfer.effectAllowed = 'move'
  }

  return (
    <div
      style={{
        width: 160,
        flexShrink: 0,
        background: 'rgba(15, 23, 42, 0.8)',
        borderRight: '1px solid rgba(148, 163, 184, 0.1)',
        padding: '16px 10px',
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        overflowY: 'auto',
      }}
    >
      <div
        style={{
          fontSize: 11,
          fontWeight: 700,
          color: '#64748b',
          textTransform: 'uppercase',
          letterSpacing: 1,
          marginBottom: 6,
          padding: '0 4px',
        }}
      >
        节点类型
      </div>

      {NODE_PALETTE.map(({ type, config }) => (
        <div
          key={type}
          draggable
          onDragStart={(e) => onDragStart(e, type)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '9px 10px',
            borderRadius: 8,
            cursor: 'grab',
            background: 'rgba(30, 41, 59, 0.5)',
            border: '1px solid rgba(148, 163, 184, 0.08)',
            transition: 'all 0.15s ease',
            userSelect: 'none',
          }}
          onMouseEnter={(e) => {
            const el = e.currentTarget
            el.style.background = 'rgba(99, 102, 241, 0.12)'
            el.style.borderColor = 'rgba(99, 102, 241, 0.3)'
          }}
          onMouseLeave={(e) => {
            const el = e.currentTarget
            el.style.background = 'rgba(30, 41, 59, 0.5)'
            el.style.borderColor = 'rgba(148, 163, 184, 0.08)'
          }}
        >
          <span
            style={{
              width: 24,
              height: 24,
              borderRadius: 6,
              background: `${config.color}22`,
              border: `1px solid ${config.color}44`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 12,
              flexShrink: 0,
            }}
          >
            {config.icon}
          </span>
          <span
            style={{
              color: '#cbd5e1',
              fontSize: 12,
              fontWeight: 500,
            }}
          >
            {config.label}
          </span>
        </div>
      ))}
    </div>
  )
}

export default memo(NodePalette)
