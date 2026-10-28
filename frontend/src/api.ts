import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'

const ACCESS = 'eco.access'
const REFRESH = 'eco.refresh'

function read(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key)
    else localStorage.setItem(key, value)
  } catch {
    /* storage unavailable (private mode); the session just won't persist */
  }
}

export const tokens = {
  get access() {
    return read(ACCESS)
  },
  get refresh() {
    return read(REFRESH)
  },
  set(access: string, refresh?: string) {
    write(ACCESS, access)
    if (refresh) write(REFRESH, refresh)
  },
  clear() {
    write(ACCESS, null)
    write(REFRESH, null)
  },
}

export const api = axios.create({ baseURL: '/api', timeout: 60000 })

api.interceptors.request.use((config) => {
  const token = tokens.access
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

let refreshing: Promise<string | null> | null = null

async function refreshAccess(): Promise<string | null> {
  const refresh = tokens.refresh
  if (!refresh) return null
  try {
    const { data } = await axios.post('/api/auth/refresh/', { refresh })
    tokens.set(data.access, data.refresh)
    return data.access
  } catch {
    return null
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined
    if (error.response?.status === 401 && original && !original._retry && !original.url?.includes('auth/')) {
      original._retry = true
      refreshing = refreshing ?? refreshAccess().finally(() => (refreshing = null))
      const access = await refreshing
      if (access) {
        original.headers.Authorization = `Bearer ${access}`
        return api(original)
      }
      tokens.clear()
      window.dispatchEvent(new Event('eco:logout'))
    }
    return Promise.reject(error)
  },
)

export async function get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const { data } = await api.get<T>(url, { params })
  return data
}

/** Turns any API error into one readable sentence. */
export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (!error.response) return 'Cannot reach the server. Is the Django backend running on port 8010?'
    const data = error.response.data as unknown
    if (data && typeof data === 'object' && !(data instanceof Blob)) {
      const record = data as Record<string, unknown>
      if (typeof record.detail === 'string') return record.detail
      const first = Object.entries(record)[0]
      if (first) {
        const [field, value] = first
        const text = Array.isArray(value) ? value.join(' ') : String(value)
        return field === 'non_field_errors' ? text : `${field.replace(/_/g, ' ')}: ${text}`
      }
    }
    return `Request failed (${error.response.status})`
  }
  return error instanceof Error ? error.message : 'Something went wrong'
}

export async function download(url: string, params: Record<string, unknown>, fallbackName: string) {
  const response = await api.get(url, { params, responseType: 'blob' })
  const disposition = String(response.headers['content-disposition'] ?? '')
  const match = /filename="([^"]+)"/.exec(disposition)
  const href = URL.createObjectURL(response.data as Blob)
  const link = document.createElement('a')
  link.href = href
  link.download = match?.[1] ?? fallbackName
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(href), 1000)
}
