import client from './client'

export interface NotificationItem {
  id: string
  title: string
  content: string
  type: 'info' | 'success' | 'warning' | 'error'
  isRead: boolean
  createdAt: string
}

export interface NotificationListResponse {
  items: NotificationItem[]
  total: number
  page: number
  size: number
  pages: number
  unreadCount: number
}

export async function getNotifications(
  page = 1,
  size = 20,
): Promise<NotificationListResponse> {
  const res = await client.get<NotificationListResponse>('/notifications', {
    params: { page, size },
  })
  return res.data
}

export async function getUnreadCount(): Promise<number> {
  const res = await client.get<{ count: number }>('/notifications/unread-count')
  return res.data.count
}

export async function markAsRead(id: string): Promise<void> {
  await client.put(`/notifications/${id}/read`)
}

export async function markAllAsRead(): Promise<void> {
  await client.put('/notifications/read-all')
}

export async function uploadFileForChat(file: File): Promise<{
  filename: string
  fileSize: number
  content: string
  truncated: boolean
}> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await client.post('/chat/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  })
  return res.data as { filename: string; fileSize: number; content: string; truncated: boolean }
}
