import client from './client'

export interface UsageSummary {
  monthly_calls: number
  monthly_tokens: number
  chat_calls: number
  mcp_calls: number
  rag_calls: number
  chat_tokens: number
}

export interface PlanInfo {
  plan: string
  monthly_calls_limit: number
  monthly_tokens_limit: number
  monthly_calls_used: number
  monthly_tokens_used: number
  calls_remaining: number
  tokens_remaining: number
}

export async function getUsage(): Promise<UsageSummary> {
  const res = await client.get<UsageSummary>('/billing/usage')
  return res.data
}

export async function getPlan(): Promise<PlanInfo> {
  const res = await client.get<PlanInfo>('/billing/plan')
  return res.data
}
