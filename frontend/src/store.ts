import { create } from 'zustand'
import { api, tokens } from './api'

export type Role = 'admin' | 'facility' | 'community'

export interface User {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  role: Role
  department: string
}

interface AuthState {
  user: User | null
  ready: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  load: () => Promise<void>
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  ready: false,
  async login(username, password) {
    const { data } = await api.post('/auth/login/', { username, password })
    tokens.set(data.access, data.refresh)
    const me = await api.get<User>('/auth/me/')
    set({ user: me.data, ready: true })
  },
  logout() {
    tokens.clear()
    set({ user: null, ready: true })
  },
  async load() {
    if (!tokens.access) {
      set({ ready: true })
      return
    }
    try {
      const me = await api.get<User>('/auth/me/')
      set({ user: me.data, ready: true })
    } catch {
      tokens.clear()
      set({ user: null, ready: true })
    }
  },
}))

export const isOperator = (user: User | null) => user?.role === 'admin' || user?.role === 'facility'
export const isAdmin = (user: User | null) => user?.role === 'admin'

export type Period = '7' | '30' | '90' | 'ytd'

interface PeriodState {
  period: Period
  setPeriod: (p: Period) => void
}

export const usePeriod = create<PeriodState>((set) => ({
  period: '30',
  setPeriod: (period) => set({ period }),
}))

export const periodParams = (period: Period) => (period === 'ytd' ? { period: 'ytd' } : { days: Number(period) })
