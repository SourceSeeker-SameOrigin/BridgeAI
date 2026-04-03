import client from './client'

export interface ChannelStatus {
  name: string
  display_name: string
  configured: boolean
  status: string
}

export async function getChannelStatus(): Promise<ChannelStatus[]> {
  const res = await client.get<ChannelStatus[]>('/channels/status')
  return res.data ?? []
}
