import axios from 'axios'
import type { ApiResponse } from '../types/common'

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor: inject token
client.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

// Response interceptor: unwrap data & handle errors
client.interceptors.response.use(
  (response) => {
    const body = response.data as ApiResponse<unknown>
    if (body.code !== 200) {
      return Promise.reject(new Error(body.message || '请求失败'))
    }
    // Unwrap: put `data.data` as response.data so callers get the inner payload directly
    response.data = body.data
    return response
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      // Avoid redirect loop if already on login page
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    }
    const apiBody = error.response?.data as ApiResponse<unknown> | undefined
    const msg = apiBody?.message || error.response?.data?.detail || error.message || '网络异常'
    return Promise.reject(new Error(msg))
  },
)

export default client
