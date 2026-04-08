import { create } from 'zustand'
import type { User } from '../types/common'
import { getMe } from '../api/auth'

interface AuthState {
  token: string | null
  user: User | null
  isAuthenticated: boolean
  loading: boolean
  setAuth: (token: string, user?: User) => void
  setUser: (user: User) => void
  logout: () => void
  /** Check existing token and load user profile */
  checkAuth: () => Promise<void>
}

const useAuthStore = create<AuthState>((set, get) => ({
  token: localStorage.getItem('token'),
  user: null,
  isAuthenticated: !!localStorage.getItem('token'),
  loading: false,

  setAuth: (token: string, user?: User) => {
    localStorage.setItem('token', token)
    set({ token, user: user ?? null, isAuthenticated: true })
  },

  setUser: (user: User) => {
    set({ user })
  },

  logout: () => {
    localStorage.removeItem('token')
    set({ token: null, user: null, isAuthenticated: false })
  },

  checkAuth: async () => {
    const { token } = get()
    if (!token) {
      set({ isAuthenticated: false, user: null })
      return
    }
    set({ loading: true })
    try {
      const user = await getMe()
      set({ user, isAuthenticated: true, loading: false })
    } catch {
      // Token invalid or expired
      localStorage.removeItem('token')
      set({ token: null, user: null, isAuthenticated: false, loading: false })
    }
  },
}))

export default useAuthStore
