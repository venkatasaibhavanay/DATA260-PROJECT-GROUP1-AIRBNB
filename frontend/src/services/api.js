// Centralised API configuration. Base URLs come from VITE_* variables in the
// repository-root .env. Never hardcode ports in components.
import axios from 'axios'

export const API_URLS = {
  users: import.meta.env.VITE_USER_API_URL,
  properties: import.meta.env.VITE_PROPERTY_API_URL,
  bookings: import.meta.env.VITE_BOOKING_API_URL,
  messaging: import.meta.env.VITE_MESSAGING_API_URL,
  ai: import.meta.env.VITE_AI_API_URL,
  analytics: import.meta.env.VITE_ANALYTICS_API_URL,
}

function createClient(baseURL) {
  const client = axios.create({ baseURL, timeout: 5000 })
  client.interceptors.request.use((config) => {
    // Trace id propagated to the backend (see docs/API_CONVENTIONS.md).
    config.headers['X-Trace-Id'] = crypto.randomUUID()
    return config
  })
  return client
}

export const api = Object.fromEntries(
  Object.entries(API_URLS).map(([key, url]) => [key, createClient(url)]),
)

export async function getServiceHealth(key) {
  const { data } = await api[key].get('/health')
  return data
}
