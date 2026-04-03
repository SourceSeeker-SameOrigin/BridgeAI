import client from './client'
import type { PageResponse } from '../types/common'
import type { KnowledgeBase, KnowledgeDocument } from '../types/chat'

/** Backend knowledge base response shape */
interface BackendKnowledgeBase {
  id: string
  name: string
  description?: string
  embedding_model: string
  chunk_size: number
  chunk_overlap: number
  status: string
  document_count: number
  total_size: number
  created_at: string
  updated_at: string
}

/** Backend document response shape */
interface BackendDocument {
  id: string
  knowledge_base_id: string
  filename: string
  file_type: string
  file_size: number
  status: string
  chunk_count: number
  error_message?: string
  created_at: string
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function mapKnowledgeBase(b: BackendKnowledgeBase): KnowledgeBase {
  return {
    id: b.id,
    name: b.name,
    description: b.description || '',
    documentCount: b.document_count ?? 0,
    totalSize: b.total_size ? formatFileSize(b.total_size) : '-',
    status: (b.status === 'active' ? 'ready' : b.status) as KnowledgeBase['status'],
    createdAt: b.created_at,
    updatedAt: b.updated_at,
  }
}

function mapDocument(b: BackendDocument): KnowledgeDocument {
  const statusMap: Record<string, KnowledgeDocument['status']> = {
    indexed: 'indexed',
    processing: 'indexing',
    ready: 'indexed',
    failed: 'failed',
    error: 'failed',
  }
  return {
    id: b.id,
    name: b.filename,
    type: b.file_type,
    size: formatFileSize(b.file_size),
    status: statusMap[b.status] || 'indexing',
    createdAt: b.created_at,
  }
}

export async function getKnowledgeBases(page = 1, size = 50): Promise<KnowledgeBase[]> {
  const res = await client.get<PageResponse<BackendKnowledgeBase>>('/knowledge', {
    params: { page, size },
  })
  return (res.data.items || []).map(mapKnowledgeBase)
}

export async function createKnowledgeBase(
  data: { name: string; description?: string },
): Promise<KnowledgeBase> {
  const res = await client.post<BackendKnowledgeBase>('/knowledge', data)
  return mapKnowledgeBase(res.data)
}

export async function deleteKnowledgeBase(id: string): Promise<void> {
  await client.delete(`/knowledge/${id}`)
}

export async function getDocuments(kbId: string, page = 1, size = 50): Promise<KnowledgeDocument[]> {
  const res = await client.get<PageResponse<BackendDocument>>(`/knowledge/${kbId}/documents`, {
    params: { page, size },
  })
  return (res.data.items || []).map(mapDocument)
}

export async function uploadDocument(kbId: string, file: File): Promise<KnowledgeDocument> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await client.post<BackendDocument>(`/knowledge/${kbId}/documents`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
  return mapDocument(res.data)
}

export async function deleteDocument(kbId: string, docId: string): Promise<void> {
  await client.delete(`/knowledge/${kbId}/documents/${docId}`)
}

interface SearchResultItem {
  chunk_id: string
  content: string
  similarity: number
  chunk_index?: number
  document_id?: string
}

export async function searchKnowledgeBase(
  kbId: string,
  query: string,
  topK = 5,
): Promise<SearchResultItem[]> {
  const res = await client.post<{ query: string; results: SearchResultItem[]; total: number }>(
    `/knowledge/${kbId}/search`,
    { query, top_k: topK },
  )
  return res.data.results || []
}
