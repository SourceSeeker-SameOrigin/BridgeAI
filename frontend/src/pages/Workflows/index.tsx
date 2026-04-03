import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { Button, Input, Modal, Spin, Popconfirm, message } from 'antd'
import {
  PlusOutlined,
  DeleteOutlined,
  SaveOutlined,
  LoadingOutlined,
  ThunderboltOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import {
  ReactFlow,
  addEdge,
  useNodesState,
  useEdgesState,
  Controls,
  MiniMap,
  Background,
  BackgroundVariant,
  MarkerType,
  type Connection,
  type Edge,
  type Node,
  type NodeTypes,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import FlowNode from './FlowNode'
import NodePalette from './NodePalette'
import NodeConfigPanel from './NodeConfigPanel'
import { NODE_TYPES } from './nodeTypes'
import {
  getWorkflows,
  createWorkflow,
  updateWorkflow,
  deleteWorkflow,
  executeWorkflow,
  type Workflow,
  type WorkflowNodeData,
  type WorkflowExecuteResult,
} from '../../api/workflows'

/* -- Custom node types registered for React Flow -- */
const nodeTypes: NodeTypes = {
  flowNode: FlowNode,
}

/** Default edge style */
const defaultEdgeOptions = {
  style: { stroke: 'rgba(148,163,184,0.4)', strokeWidth: 2 },
  markerEnd: { type: MarkerType.ArrowClosed, color: 'rgba(148,163,184,0.4)' },
  animated: true,
}

function generateNodeId(): string {
  return `node_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

export default function WorkflowsPage() {
  const { t } = useTranslation()

  /* -- Workflow list state -- */
  const [workflows, setWorkflows] = useState<Workflow[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')

  /* -- React Flow state -- */
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<WorkflowNodeData>>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const reactFlowInstance = useRef<{ screenToFlowPosition: (pos: { x: number; y: number }) => { x: number; y: number } } | null>(null)

  /* -- Execute state -- */
  const [executeModalOpen, setExecuteModalOpen] = useState(false)
  const [executeInput, setExecuteInput] = useState('')
  const [executing, setExecuting] = useState(false)
  const [executeResult, setExecuteResult] = useState<WorkflowExecuteResult | null>(null)

  const selected = useMemo(() => workflows.find((w) => w.id === selectedId) ?? null, [workflows, selectedId])
  const selectedNode = useMemo(() => nodes.find((n) => n.id === selectedNodeId) ?? null, [nodes, selectedNodeId])

  /* -- Load workflows -- */
  const loadWorkflows = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getWorkflows()
      setWorkflows(data)
    } catch (err) {
      message.error(`${t('workflows.loadFailed')}: ${(err as Error).message}`)
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    loadWorkflows()
  }, [loadWorkflows])

  /* -- Select workflow -> load nodes/edges -- */
  const handleSelect = useCallback(
    (wf: Workflow) => {
      setSelectedId(wf.id)
      setSelectedNodeId(null)

      if (wf.nodes.length > 0) {
        setNodes(wf.nodes as Node<WorkflowNodeData>[])
        setEdges(
          wf.edges.map((e) => ({
            ...e,
            style: defaultEdgeOptions.style,
            markerEnd: defaultEdgeOptions.markerEnd,
            animated: true,
          })),
        )
      } else {
        // New workflow: add a default start node
        const startNode: Node<WorkflowNodeData> = {
          id: generateNodeId(),
          type: 'flowNode',
          position: { x: 100, y: 200 },
          data: {
            nodeType: 'start',
            label: t('workflows.startNode'),
            config: {},
          },
        }
        setNodes([startNode])
        setEdges([])
      }
    },
    [setNodes, setEdges, t],
  )

  /* -- Create workflow -- */
  const handleCreate = async () => {
    if (!newName.trim()) {
      message.warning(t('workflows.nameRequired'))
      return
    }
    try {
      const wf = await createWorkflow({ name: newName.trim(), description: newDesc.trim() })
      setWorkflows((prev) => [...prev, wf])
      handleSelect(wf)
      setCreateModalOpen(false)
      setNewName('')
      setNewDesc('')
      message.success(t('workflows.created'))
    } catch (err) {
      message.error(`${t('common.createFailed')}: ${(err as Error).message}`)
    }
  }

  /* -- Delete workflow -- */
  const handleDelete = async (id: string) => {
    try {
      await deleteWorkflow(id)
      setWorkflows((prev) => prev.filter((w) => w.id !== id))
      if (selectedId === id) {
        setSelectedId(null)
        setNodes([])
        setEdges([])
        setSelectedNodeId(null)
      }
      message.success(t('workflows.deleted'))
    } catch (err) {
      message.error(`${t('common.deleteFailed')}: ${(err as Error).message}`)
    }
  }

  /* -- Save -- */
  const handleSave = async () => {
    if (!selectedId) return
    setSaving(true)
    try {
      const flowNodes = nodes.map((n) => ({
        id: n.id,
        type: 'flowNode',
        position: n.position,
        data: n.data,
      }))
      const flowEdges = edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle ?? undefined,
        targetHandle: e.targetHandle ?? undefined,
      }))
      const updated = await updateWorkflow(selectedId, {
        nodes: flowNodes,
        edges: flowEdges,
      })
      setWorkflows((prev) => prev.map((w) => (w.id === selectedId ? updated : w)))
      message.success(t('workflows.saved'))
    } catch (err) {
      message.error(`${t('common.saveFailed')}: ${(err as Error).message}`)
    } finally {
      setSaving(false)
    }
  }

  /* -- Execute workflow -- */
  const handleExecute = async () => {
    if (!selectedId) return
    setExecuting(true)
    try {
      const result = await executeWorkflow(selectedId, executeInput)
      setExecuteResult(result)
      if (result.status === 'completed') {
        message.success(t('workflows.completed'))
      } else {
        message.warning(t('workflows.executeWarning'))
      }
    } catch (err) {
      message.error(`${t('workflows.executeFailed')}: ${(err as Error).message}`)
    } finally {
      setExecuting(false)
    }
  }

  /* -- React Flow event handlers -- */
  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) =>
        addEdge(
          {
            ...connection,
            style: defaultEdgeOptions.style,
            markerEnd: defaultEdgeOptions.markerEnd,
            animated: true,
          },
          eds,
        ),
      )
    },
    [setEdges],
  )

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNodeId(node.id)
  }, [])

  const onPaneClick = useCallback(() => {
    setSelectedNodeId(null)
  }, [])

  /* -- Drag & Drop from palette -- */
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()

      const nodeType = event.dataTransfer.getData('application/reactflow-nodetype')
      if (!nodeType || !NODE_TYPES[nodeType]) return

      const config = NODE_TYPES[nodeType]
      const position = reactFlowInstance.current?.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      }) ?? { x: 0, y: 0 }

      const newNode: Node<WorkflowNodeData> = {
        id: generateNodeId(),
        type: 'flowNode',
        position,
        data: {
          nodeType: nodeType,
          label: config.label,
          config: {},
        },
      }
      setNodes((nds) => [...nds, newNode])
    },
    [setNodes],
  )

  /* -- Node config panel handlers -- */
  const handleNodeUpdate = useCallback(
    (nodeId: string, updates: Partial<WorkflowNodeData>) => {
      setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId
            ? { ...n, data: { ...n.data, ...updates } }
            : n,
        ),
      )
    },
    [setNodes],
  )

  const handleNodeDelete = useCallback(
    (nodeId: string) => {
      setNodes((nds) => nds.filter((n) => n.id !== nodeId))
      setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId))
      setSelectedNodeId(null)
    },
    [setNodes, setEdges],
  )

  /* -- Keyboard shortcut: Delete/Backspace to remove selected nodes -- */
  const onKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if ((event.key === 'Delete' || event.key === 'Backspace') && selectedNodeId) {
        // Don't delete if focus is in an input
        const tag = (event.target as HTMLElement).tagName
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
        handleNodeDelete(selectedNodeId)
      }
    },
    [selectedNodeId, handleNodeDelete],
  )

  return (
    <div
      className="animate-fade-in"
      style={{ height: '100%', display: 'flex', flexDirection: 'column' }}
      onKeyDown={onKeyDown}
      tabIndex={0}
    >
      {/* Top bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '0 0 16px 0',
          flexShrink: 0,
        }}
      >
        <h2 style={{ fontSize: 22, fontWeight: 700, color: '#f1f5f9', margin: 0 }}>
          {t('workflows.title')}
        </h2>
        {selected && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ color: '#94a3b8', fontSize: 14 }}>
              {selected.name}
            </span>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              loading={saving}
              onClick={handleSave}
            >
              {t('workflows.save')}
            </Button>
            <Button
              icon={<PlayCircleOutlined />}
              onClick={() => {
                setExecuteInput('')
                setExecuteResult(null)
                setExecuteModalOpen(true)
              }}
              style={{
                borderColor: 'rgba(99,102,241,0.4)',
                color: '#a5b4fc',
              }}
            >
              {t('workflows.run')}
            </Button>
          </div>
        )}
      </div>

      {/* Main content */}
      <div
        style={{
          display: 'flex',
          flex: 1,
          gap: 0,
          borderRadius: 12,
          overflow: 'hidden',
          border: '1px solid rgba(148,163,184,0.1)',
          background: '#0a0e1a',
          minHeight: 0,
        }}
      >
        {/* Left: workflow list */}
        <div
          style={{
            width: 220,
            flexShrink: 0,
            background: 'rgba(15, 23, 42, 0.6)',
            borderRight: '1px solid rgba(148,163,184,0.1)',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <div style={{ padding: '12px 10px', borderBottom: '1px solid rgba(148,163,184,0.08)' }}>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              block
              size="small"
              onClick={() => setCreateModalOpen(true)}
            >
              {t('workflows.create')}
            </Button>
          </div>
          <div style={{ flex: 1, overflow: 'auto', padding: '8px 6px' }}>
            {loading ? (
              <div style={{ textAlign: 'center', padding: 40 }}>
                <Spin indicator={<LoadingOutlined style={{ fontSize: 20, color: '#6366f1' }} />} />
              </div>
            ) : workflows.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 30, color: '#475569', fontSize: 12 }}>
                {t('workflows.noWorkflows')}
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {workflows.map((wf) => (
                  <div
                    key={wf.id}
                    onClick={() => handleSelect(wf)}
                    style={{
                      padding: '10px 12px',
                      borderRadius: 8,
                      background:
                        selectedId === wf.id
                          ? 'rgba(99,102,241,0.15)'
                          : 'transparent',
                      border:
                        selectedId === wf.id
                          ? '1px solid rgba(99,102,241,0.35)'
                          : '1px solid transparent',
                      cursor: 'pointer',
                      transition: 'all 0.15s',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                    onMouseEnter={(e) => {
                      if (selectedId !== wf.id) {
                        e.currentTarget.style.background = 'rgba(51,65,85,0.3)'
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (selectedId !== wf.id) {
                        e.currentTarget.style.background = 'transparent'
                      }
                    }}
                  >
                    <div style={{ overflow: 'hidden' }}>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                        }}
                      >
                        <ThunderboltOutlined
                          style={{
                            color: selectedId === wf.id ? '#818cf8' : '#475569',
                            fontSize: 12,
                          }}
                        />
                        <span
                          style={{
                            color: selectedId === wf.id ? '#e2e8f0' : '#94a3b8',
                            fontWeight: 600,
                            fontSize: 13,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {wf.name}
                        </span>
                      </div>
                      {wf.description && (
                        <div
                          style={{
                            fontSize: 11,
                            color: '#475569',
                            marginTop: 2,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            maxWidth: 140,
                          }}
                        >
                          {wf.description}
                        </div>
                      )}
                    </div>
                    <Popconfirm
                      title={t('workflows.confirmDelete')}
                      onConfirm={(e) => {
                        e?.stopPropagation()
                        handleDelete(wf.id)
                      }}
                      onCancel={(e) => e?.stopPropagation()}
                    >
                      <Button
                        type="text"
                        size="small"
                        icon={<DeleteOutlined />}
                        onClick={(e) => e.stopPropagation()}
                        style={{ color: '#475569', fontSize: 11, opacity: 0.6 }}
                      />
                    </Popconfirm>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Middle: Node palette */}
        {selected && <NodePalette />}

        {/* Right: Canvas area */}
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            minWidth: 0,
          }}
        >
          {selected ? (
            <>
              {/* Canvas */}
              <div ref={reactFlowWrapper} style={{ flex: 1, minHeight: 0 }}>
                <ReactFlow
                  nodes={nodes}
                  edges={edges}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  onConnect={onConnect}
                  onNodeClick={onNodeClick}
                  onPaneClick={onPaneClick}
                  onDragOver={onDragOver}
                  onDrop={onDrop}
                  onInit={(instance) => {
                    reactFlowInstance.current = instance
                  }}
                  nodeTypes={nodeTypes}
                  defaultEdgeOptions={defaultEdgeOptions}
                  fitView
                  fitViewOptions={{ padding: 0.3 }}
                  proOptions={{ hideAttribution: true }}
                  colorMode="dark"
                  style={{ background: '#0a0e1a' }}
                  deleteKeyCode={null}
                >
                  <Controls
                    style={{
                      background: 'rgba(15,23,42,0.9)',
                      border: '1px solid rgba(148,163,184,0.1)',
                      borderRadius: 8,
                    }}
                  />
                  <MiniMap
                    style={{
                      background: 'rgba(15,23,42,0.9)',
                      border: '1px solid rgba(148,163,184,0.1)',
                      borderRadius: 8,
                    }}
                    nodeColor={(n) => {
                      const nd = n.data as unknown as WorkflowNodeData
                      return NODE_TYPES[nd.nodeType]?.color ?? '#64748b'
                    }}
                    maskColor="rgba(0,0,0,0.5)"
                  />
                  <Background
                    variant={BackgroundVariant.Dots}
                    gap={20}
                    size={1}
                    color="rgba(148,163,184,0.08)"
                  />
                </ReactFlow>
              </div>

              {/* Bottom: Config panel */}
              {selectedNode && (
                <NodeConfigPanel
                  nodeId={selectedNode.id}
                  data={selectedNode.data}
                  onUpdate={handleNodeUpdate}
                  onDelete={handleNodeDelete}
                  onClose={() => setSelectedNodeId(null)}
                />
              )}
            </>
          ) : (
            <div
              style={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexDirection: 'column',
                gap: 12,
                color: '#475569',
              }}
            >
              <ThunderboltOutlined style={{ fontSize: 48, opacity: 0.3 }} />
              <span style={{ fontSize: 14 }}>{t('workflows.selectOrCreate')}</span>
            </div>
          )}
        </div>
      </div>

      {/* Create modal */}
      <Modal
        title={t('workflows.createTitle')}
        open={createModalOpen}
        onOk={handleCreate}
        onCancel={() => {
          setCreateModalOpen(false)
          setNewName('')
          setNewDesc('')
        }}
        okText={t('common.create')}
        cancelText={t('common.cancel')}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 16 }}>
          <div>
            <div style={{ marginBottom: 4, fontSize: 13, color: '#cbd5e1' }}>{t('common.name')}</div>
            <Input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder={t('workflows.namePlaceholder')}
            />
          </div>
          <div>
            <div style={{ marginBottom: 4, fontSize: 13, color: '#cbd5e1' }}>{t('common.description')}</div>
            <Input.TextArea
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              placeholder={t('workflows.descPlaceholder')}
              autoSize={{ minRows: 2, maxRows: 4 }}
            />
          </div>
        </div>
      </Modal>

      {/* Execute modal */}
      <Modal
        title={t('workflows.runTitle')}
        open={executeModalOpen}
        onCancel={() => {
          setExecuteModalOpen(false)
          setExecuteInput('')
          setExecuteResult(null)
        }}
        footer={
          executeResult ? (
            <Button onClick={() => {
              setExecuteModalOpen(false)
              setExecuteInput('')
              setExecuteResult(null)
            }}>
              {t('common.close')}
            </Button>
          ) : (
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <Button onClick={() => setExecuteModalOpen(false)}>{t('common.cancel')}</Button>
              <Button type="primary" loading={executing} onClick={handleExecute}>
                {t('workflows.startExecute')}
              </Button>
            </div>
          )
        }
        width={600}
      >
        {!executeResult ? (
          <div style={{ marginTop: 16 }}>
            <div style={{ marginBottom: 4, fontSize: 13, color: '#cbd5e1' }}>
              {t('workflows.inputLabel')}
            </div>
            <Input.TextArea
              value={executeInput}
              onChange={(e) => setExecuteInput(e.target.value)}
              placeholder={t('workflows.inputPlaceholder')}
              autoSize={{ minRows: 3, maxRows: 6 }}
            />
          </div>
        ) : (
          <div style={{ marginTop: 16 }}>
            <div style={{ marginBottom: 12 }}>
              <span style={{ fontWeight: 600, marginRight: 8 }}>{t('workflows.statusLabel')}</span>
              <span
                style={{
                  color: executeResult.status === 'completed' ? '#22c55e' : '#ef4444',
                  fontWeight: 500,
                }}
              >
                {executeResult.status === 'completed' ? t('workflows.completed') : t('workflows.failed')}
              </span>
            </div>
            {executeResult.steps.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 13 }}>{t('workflows.steps')}</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {executeResult.steps.map((step, idx) => (
                    <div
                      key={step.node_id}
                      style={{
                        padding: '8px 12px',
                        borderRadius: 6,
                        background: step.status === 'success'
                          ? 'rgba(34,197,94,0.08)'
                          : 'rgba(239,68,68,0.08)',
                        border: `1px solid ${step.status === 'success' ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}`,
                        fontSize: 13,
                      }}
                    >
                      <div style={{ fontWeight: 500 }}>
                        {t('workflows.stepLabel', { num: idx + 1 })}: {step.node_type}
                        <span
                          style={{
                            marginLeft: 8,
                            fontSize: 11,
                            color: step.status === 'success' ? '#22c55e' : '#ef4444',
                          }}
                        >
                          {step.status === 'success' ? t('workflows.stepSuccess') : t('workflows.stepFailed')}
                        </span>
                      </div>
                      {step.output && (
                        <div style={{ marginTop: 4, color: '#94a3b8', fontSize: 12, wordBreak: 'break-all' }}>
                          {step.output}
                        </div>
                      )}
                      {step.error && (
                        <div style={{ marginTop: 4, color: '#ef4444', fontSize: 12 }}>
                          {step.error}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div>
              <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 13 }}>{t('workflows.finalOutput')}</div>
              <div
                style={{
                  padding: '8px 12px',
                  borderRadius: 6,
                  background: 'rgba(99,102,241,0.08)',
                  border: '1px solid rgba(99,102,241,0.2)',
                  fontSize: 13,
                  wordBreak: 'break-all',
                }}
              >
                {executeResult.final_output || t('workflows.noOutput')}
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
