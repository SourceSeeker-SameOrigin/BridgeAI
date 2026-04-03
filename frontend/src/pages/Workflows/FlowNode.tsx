import { memo } from 'react'
import { Handle, Position } from '@xyflow/react'
import type { NodeProps, Node } from '@xyflow/react'
import { NODE_TYPES } from './nodeTypes'
import type { WorkflowNodeData } from '../../api/workflows'

type FlowNodeType = Node<WorkflowNodeData, 'flowNode'>

function FlowNode({ data, selected }: NodeProps<FlowNodeType>) {
  const config = NODE_TYPES[data.nodeType]
  if (!config) return null

  const isStart = data.nodeType === 'start'
  const isCondition = data.nodeType === 'condition'
  const isLoop = data.nodeType === 'loop'

  return (
    <div
      style={{
        background: '#1a2332',
        border: selected
          ? `2px solid ${config.color}`
          : '1px solid rgba(148,163,184,0.15)',
        borderRadius: 10,
        minWidth: 200,
        maxWidth: 260,
        boxShadow: selected
          ? `0 0 16px ${config.color}30, 0 4px 12px rgba(0,0,0,0.3)`
          : '0 2px 8px rgba(0,0,0,0.2)',
        transition: 'border-color 0.2s, box-shadow 0.2s',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          background: `linear-gradient(135deg, ${config.color}, ${config.color}cc)`,
          padding: '7px 14px',
          display: 'flex',
          alignItems: 'center',
          gap: 7,
        }}
      >
        <span style={{ fontSize: 14 }}>{config.icon}</span>
        <span
          style={{
            color: '#fff',
            fontWeight: 600,
            fontSize: 13,
            letterSpacing: 0.3,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {data.label}
        </span>
      </div>

      {/* Body */}
      <div
        style={{
          padding: '10px 14px',
          fontSize: 12,
          color: '#94a3b8',
          lineHeight: 1.5,
        }}
      >
        {data.description || config.defaultDesc}
      </div>

      {/* Handles */}
      {!isStart && (
        <Handle
          type="target"
          position={Position.Left}
          style={{
            width: 10,
            height: 10,
            background: '#334155',
            border: '2px solid #64748b',
            borderRadius: '50%',
          }}
        />
      )}

      {/* Default source handle (right side) */}
      <Handle
        type="source"
        position={Position.Right}
        id="default"
        style={{
          width: 10,
          height: 10,
          background: config.color,
          border: `2px solid ${config.color}`,
          borderRadius: '50%',
        }}
      />

      {/* Condition node: true/false handles */}
      {isCondition && (
        <>
          <Handle
            type="source"
            position={Position.Bottom}
            id="false"
            style={{
              width: 10,
              height: 10,
              background: '#ef4444',
              border: '2px solid #ef4444',
              borderRadius: '50%',
              left: '30%',
            }}
          />
          <div
            style={{
              position: 'absolute',
              bottom: -20,
              left: 'calc(30% - 10px)',
              fontSize: 10,
              color: '#ef4444',
              fontWeight: 600,
            }}
          >
            False
          </div>
          <div
            style={{
              position: 'absolute',
              right: -32,
              top: '50%',
              transform: 'translateY(-50%)',
              fontSize: 10,
              color: config.color,
              fontWeight: 600,
            }}
          >
            True
          </div>
        </>
      )}

      {/* Loop node: loop-back handle */}
      {isLoop && (
        <>
          <Handle
            type="source"
            position={Position.Bottom}
            id="loop"
            style={{
              width: 10,
              height: 10,
              background: '#22c55e',
              border: '2px solid #22c55e',
              borderRadius: '50%',
            }}
          />
          <div
            style={{
              position: 'absolute',
              bottom: -20,
              left: '50%',
              transform: 'translateX(-50%)',
              fontSize: 10,
              color: '#22c55e',
              fontWeight: 600,
            }}
          >
            Loop
          </div>
        </>
      )}
    </div>
  )
}

export default memo(FlowNode)
