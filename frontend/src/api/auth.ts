import client from './client'
import type { LoginRequest, LoginResponse, RegisterRequest, User } from '../types/common'

export async function login(data: LoginRequest): Promise<LoginResponse> {
  const res = await client.post<LoginResponse>('/auth/login', data)
  return res.data
}

export async function register(data: RegisterRequest): Promise<LoginResponse> {
  // Register returns user, then we need to login separately
  await client.post('/auth/register', data)
  // Auto-login after register
  const loginRes = await client.post<LoginResponse>('/auth/login', {
    username: data.username,
    password: data.password,
  })
  return loginRes.data
}

export async function getMe(): Promise<User> {
  const res = await client.get<User>('/auth/me')
  return res.data
}
