import { memo } from 'react'
import { Input, Select, Slider } from 'antd'
import { CloseOutlined, DeleteOutlined } from '@ant-design/icons'
import { NODE_TYPES } from './nodeTypes'
import type { WorkflowNodeData } from '../../api/workflows'

interface NodeConfigPanelProps {
  nodeId: string
  data: WorkflowNodeData
  onUpdate: (nodeId: string, updates: Partial<WorkflowNodeData>) => void
  onDelete: (nodeId: string) => void
  onClose: () => void
}

function NodeConfigPanel({ nodeId, data, onUpdate, onDelete, onClose }: NodeConfigPanelProps) {
  const config = NODE_TYPES[data.nodeType]
  if (!config) return null

  const updateConfig = (key: string, value: unknown) => {
    onUpdate(nodeId, {
      config: { ...data.config, [key]: value },
    })
  }

  return (
    <div
      style={{
        background: 'rgba(15, 23, 42, 0.95)',
        borderTop: '1px solid rgba(148, 163, 184, 0.12)',
        padding: '16px 24px',
        display: 'flex',
        gap: 24,
        alignItems: 'flex-start',
        backdropFilter: 'blur(12px)',
        maxHeight: 220,
        overflowY: 'auto',
      }}
    >
      {/* Left: meta info */}
      <div style={{ minWidth: 200, flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <span
            style={{
              width: 28,
              height: 28,
              borderRadius: 7,
              background: `${config.color}22`,
              border: `1px solid ${config.color}55`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 14,
            }}
          >
            {config.icon}
          </span>
          <span style={{ color: config.color, fontWeight: 700, fontSize: 14 }}>
            {config.label}
          </span>
        </div>

        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 3 }}>节点名称</div>
          <Input
            size="small"
            value={data.label}
            onChange={(e) => onUpdate(nodeId, { label: e.target.value })}
            style={{ background: 'rgba(0,0,0,0.3)', width: 180 }}
          />
        </div>

        <div>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 3 }}>描述</div>
          <Input
            size="small"
            value={data.description || ''}
            onChange={(e) => onUpdate(nodeId, { description: e.target.value })}
            style={{ background: 'rgba(0,0,0,0.3)', width: 180 }}
            placeholder="可选描述"
          />
        </div>
      </div>

      {/* Divider */}
      <div
        style={{
          width: 1,
          alignSelf: 'stretch',
          background: 'rgba(148, 163, 184, 0.1)',
        }}
      />

      {/* Right: config fields */}
      <div style={{ flex: 1, display: 'flex', flexWrap: 'wrap', gap: 16 }}>
        {config.configFields.map((field) => {
          const val = data.config[field.key]
          return (
            <div
              key={field.key}
              style={{
                flex: field.type === 'textarea' ? '1 1 100%' : '1 1 200px',
                maxWidth: field.type === 'textarea' ? '100%' : 300,
              }}
            >
              <div style={{ fontSize: 11, color: '#64748b', marginBottom: 3 }}>
                {field.label}
              </div>
              {field.type === 'select' && (
                <Select
                  size="small"
                  value={(val as string) || undefined}
                  onChange={(v) => updateConfig(field.key, v)}
                  options={field.options}
                  style={{ width: '100%' }}
                  placeholder={field.placeholder || `选择${field.label}`}
                />
              )}
              {field.type === 'text' && (
                <Input
                  size="small"
                  value={val !== undefined ? String(val) : ''}
                  onChange={(e) => updateConfig(field.key, e.target.value)}
                  style={{ background: 'rgba(0,0,0,0.3)' }}
                  placeholder={field.placeholder}
                />
              )}
              {field.type === 'textarea' && (
                <Input.TextArea
                  size="small"
                  autoSize={{ minRows: 2, maxRows: 4 }}
                  value={
                    val !== undefined
                      ? typeof val === 'string'
                        ? val
                        : JSON.stringify(val, null, 2)
                      : ''
                  }
                  onChange={(e) => updateConfig(field.key, e.target.value)}
                  style={{
                    background: 'rgba(0,0,0,0.3)',
                    fontFamily: 'monospace',
                    fontSize: 12,
                  }}
                  placeholder={field.placeholder}
                />
              )}
              {field.type === 'slider' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <Slider
                    min={field.min ?? 0}
                    max={field.max ?? 1}
                    step={field.step ?? 0.1}
                    value={typeof val === 'number' ? val : (field.defaultValue as number) ?? 0.7}
                    onChange={(v) => updateConfig(field.key, v)}
                    style={{ flex: 1 }}
                  />
                  <span style={{ fontSize: 12, color: '#94a3b8', minWidth: 28 }}>
                    {typeof val === 'number' ? val : (field.defaultValue as number) ?? 0.7}
                  </span>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flexShrink: 0 }}>
        <button
          onClick={onClose}
          style={{
            width: 28,
            height: 28,
            borderRadius: 6,
            background: 'rgba(100,116,139,0.15)',
            border: '1px solid rgba(148,163,184,0.1)',
            color: '#94a3b8',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 12,
          }}
          title="关闭面板"
        >
          <CloseOutlined />
        </button>
        <button
          onClick={() => onDelete(nodeId)}
          style={{
            width: 28,
            height: 28,
            borderRadius: 6,
            background: 'rgba(239,68,68,0.1)',
            border: '1px solid rgba(239,68,68,0.2)',
            color: '#ef4444',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 12,
          }}
          title="删除节点"
        >
          <DeleteOutlined />
        </button>
      </div>
    </div>
  )
}

export default memo(NodeConfigPanel)
