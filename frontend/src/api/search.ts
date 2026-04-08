import client from './client'

export interface SearchResultItem {
  id: string
  name?: string
  title?: string
  description?: string
  type: 'agent' | 'knowledge_base' | 'conversation'
}

export interface SearchResults {
  agents: SearchResultItem[]
  knowledge_bases: SearchResultItem[]
  conversations: SearchResultItem[]
}

export async function globalSearch(q: string): Promise<SearchResults> {
  const res = await client.get<SearchResults>('/search', { params: { q } })
  return res.data
}
