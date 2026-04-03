import client from './client'
import type { PageResponse } from '../types/common'

/* ── Node / Edge types matching backend ── */

export interface WorkflowNodeData {
  [key: string]: unknown
  nodeType: string
  label: string
  description?: string
  config: Record<string, unknown>
}

export interface WorkflowNode {
  id: string
  type: string
  position: { x: number; y: number }
  data: WorkflowNodeData
}

export interface WorkflowEdge {
  id: string
  source: string
  target: string
  sourceHandle?: string
  targetHandle?: string
  condition?: string
}

export interface Workflow {
  id: string
  name: string
  description: string
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  status: string
  created_at: string
  updated_at: string
}

export interface CreateWorkflowRequest {
  name: string
  description: string
}

export interface UpdateWorkflowRequest {
  name?: string
  description?: string
  nodes?: WorkflowNode[]
  edges?: WorkflowEdge[]
}

/* ── Legacy step type (kept for compatibility) ── */
export interface WorkflowStep {
  id: string
  type: 'llm_call' | 'tool_call' | 'condition' | 'loop' | 'wait_input'
  name: string
  config: Record<string, unknown>
  order: number
}

/* ── Backend response shape ── */
interface BackendWorkflow {
  id: string
  name: string
  description?: string
  agent_id?: string
  nodes: Array<{
    id: string
    type: string
    config: Record<string, unknown>
    position?: { x: number; y: number }
  }>
  edges: Array<{
    source: string
    target: string
    condition?: string
  }>
  is_active: boolean
  created_at: string
  updated_at: string
}

/** Map backend node type to frontend nodeType */
function mapNodeType(backendType: string): string {
  if (backendType === 'llm') return 'llm_call'
  return backendType
}

/** Map frontend nodeType to backend type */
function unmapNodeType(frontendType: string): string {
  if (frontendType === 'llm_call') return 'llm'
  return frontendType
}

/** Map backend response to frontend Workflow */
function mapWorkflow(b: BackendWorkflow): Workflow {
  const nodes: WorkflowNode[] = (b.nodes || []).map((node, index) => ({
    id: node.id,
    type: 'flowNode',
    position: node.position || { x: index * 280, y: 100 },
    data: {
      nodeType: mapNodeType(node.type),
      label: (node.config?.name as string) || node.id,
      description: node.config?.description as string | undefined,
      config: node.config || {},
    },
  }))

  const edges: WorkflowEdge[] = (b.edges || []).map((edge, index) => ({
    id: `edge_${index}_${edge.source}_${edge.target}`,
    source: edge.source,
    target: edge.target,
    condition: edge.condition,
  }))

  return {
    id: b.id,
    name: b.name,
    description: b.description || '',
    nodes,
    edges,
    status: b.is_active ? 'active' : 'inactive',
    created_at: b.created_at,
    updated_at: b.updated_at,
  }
}

/** Map frontend nodes/edges back to backend format */
function toBackendPayload(nodes: WorkflowNode[], edges: WorkflowEdge[]): {
  nodes: Array<{ id: string; type: string; config: Record<string, unknown>; position: { x: number; y: number } }>
  edges: Array<{ source: string; target: string; condition?: string }>
} {
  return {
    nodes: nodes.map((n) => ({
      id: n.id,
      type: unmapNodeType(n.data.nodeType),
      config: {
        ...n.data.config,
        name: n.data.label,
        description: n.data.description,
      },
      position: n.position,
    })),
    edges: edges.map((e) => ({
      source: e.source,
      target: e.target,
      ...(e.condition ? { condition: e.condition } : {}),
    })),
  }
}

export async function getWorkflows(): Promise<Workflow[]> {
  const res = await client.get<PageResponse<BackendWorkflow>>('/workflows')
  return (res.data.items || []).map(mapWorkflow)
}

export async function getWorkflow(id: string): Promise<Workflow> {
  const res = await client.get<BackendWorkflow>(`/workflows/${id}`)
  return mapWorkflow(res.data)
}

export async function createWorkflow(data: CreateWorkflowRequest): Promise<Workflow> {
  const res = await client.post<BackendWorkflow>('/workflows', {
    name: data.name,
    description: data.description,
  })
  return mapWorkflow(res.data)
}

export async function updateWorkflow(id: string, data: UpdateWorkflowRequest): Promise<Workflow> {
  const payload: Record<string, unknown> = {}
  if (data.name !== undefined) payload.name = data.name
  if (data.description !== undefined) payload.description = data.description
  if (data.nodes !== undefined && data.edges !== undefined) {
    const backend = toBackendPayload(data.nodes, data.edges)
    payload.nodes = backend.nodes
    payload.edges = backend.edges
  }
  const res = await client.put<BackendWorkflow>(`/workflows/${id}`, payload)
  return mapWorkflow(res.data)
}

export async function deleteWorkflow(id: string): Promise<void> {
  await client.delete(`/workflows/${id}`)
}

/* ── Execute workflow ── */

export interface WorkflowStepResult {
  node_id: string
  node_type: string
  status: string
  output?: string
  error?: string
}

export interface WorkflowExecuteResult {
  workflow_id: string
  status: string
  steps: WorkflowStepResult[]
  final_output: string
}

export async function executeWorkflow(
  id: string,
  input: string,
  variables?: Record<string, unknown>,
): Promise<WorkflowExecuteResult> {
  const res = await client.post<WorkflowExecuteResult>(`/workflows/${id}/execute`, {
    input,
    variables: variables ?? {},
  })
  return res.data
}
