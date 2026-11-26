// Centralised API configuration. Base URLs come from VITE_* variables in the
// repository-root .env. Never hardcode ports in components.
// Conventions: docs/API_CONVENTIONS.md (success {data, meta}, error {error, meta}).
import axios from 'axios'

export const API_URLS = {
  users: import.meta.env.VITE_USER_API_URL,
  properties: import.meta.env.VITE_PROPERTY_API_URL,
  bookings: import.meta.env.VITE_BOOKING_API_URL,
  messaging: import.meta.env.VITE_MESSAGING_API_URL,
  ai: import.meta.env.VITE_AI_API_URL,
  analytics: import.meta.env.VITE_ANALYTICS_API_URL,
}

// ---- Token store (memory + sessionStorage) ---------------------------------
const TOKEN_KEY = 'g1_access_token'
let accessToken = null

function readStoredToken() {
  try {
    return window.sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token) {
  accessToken = token || null
  try {
    if (accessToken) window.sessionStorage.setItem(TOKEN_KEY, accessToken)
    else window.sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    // sessionStorage unavailable: keep the in-memory copy only
  }
}

export function getToken() {
  if (!accessToken) accessToken = readStoredToken()
  return accessToken
}

export function clearToken() {
  setToken(null)
}

// One key per user action; reuse it on retries: api.bookings.post(url, body, { idempotencyKey })
export function newIdempotencyKey() {
  return crypto.randomUUID()
}

// ---- Clients ----------------------------------------------------------------
function createClient(baseURL) {
  const client = axios.create({ baseURL, timeout: 5000 })

  client.interceptors.request.use((config) => {
    const token = getToken()
    if (token) config.headers.Authorization = `Bearer ${token}`
    config.headers['X-Trace-ID'] = config.traceId || crypto.randomUUID()
    config.headers['X-Request-ID'] = crypto.randomUUID()
    if (config.idempotencyKey) config.headers['Idempotency-Key'] = config.idempotencyKey
    return config
  })

  client.interceptors.response.use(
    (response) => {
      const body = response.data
      // Unwrap {data, meta} so components read res.data directly. Health is not wrapped.
      if (body && typeof body === 'object' && !Array.isArray(body) && 'data' in body) {
        response.meta = body.meta
        response.data = body.data
      }
      return response
    },
    (error) => {
      if (error.response?.status === 401) {
        clearToken()
        if (window.location.pathname !== '/login') window.location.assign('/login')
      }
      return Promise.reject(error)
    },
  )

  return client
}

export const api = Object.fromEntries(
  Object.entries(API_URLS).map(([key, url]) => [key, createClient(url)]),
)

// {status, code, message, fields, traceId} from any failed request.
export function getErrorInfo(err) {
  const res = err?.response
  const body = res?.data
  return {
    status: res?.status ?? null,
    code: body?.error?.code ?? (res ? `HTTP_${res.status}` : 'NETWORK_ERROR'),
    message: body?.error?.message ?? err?.message ?? 'Request failed.',
    fields: body?.error?.fields ?? null,
    traceId: body?.meta?.trace_id ?? res?.headers?.['x-trace-id'] ?? null,
  }
}

export async function getServiceHealth(key) {
  const { data } = await api[key].get('/health')
  return data
}
