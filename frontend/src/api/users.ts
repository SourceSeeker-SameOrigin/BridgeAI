import client from './client'
import type { User } from '../types/common'

export interface InviteUserRequest {
  username: string
  email: string
  role: string
}

export interface ChangeRoleRequest {
  role: string
}

export async function getUsers(): Promise<User[]> {
  const res = await client.get<User[]>('/users')
  return res.data
}

export async function inviteUser(data: InviteUserRequest): Promise<User> {
  const res = await client.post<User>('/users/invite', data)
  return res.data
}

export async function changeRole(userId: string, data: ChangeRoleRequest): Promise<User> {
  const res = await client.put<User>(`/users/${userId}/role`, data)
  return res.data
}

export async function deleteUser(userId: string): Promise<void> {
  await client.delete(`/users/${userId}`)
}
