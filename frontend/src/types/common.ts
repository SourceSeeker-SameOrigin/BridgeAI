export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export interface PageResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

export interface User {
  id: string
  username: string
  email: string
  avatar?: string
  role: string
  is_active?: boolean
  tenant_id?: string
  createdAt?: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  password: string
  email: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
}
