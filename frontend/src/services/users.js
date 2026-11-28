// user-service API calls (API doc section 6). Responses are already unwrapped by api.js,
// so `res.data` is the payload.
import { api, API_URLS } from './api.js'

const u = api.users

export const authApi = {
  login: (email, password, role) => u.post('/api/v1/auth/login', { email, password, role }),
  logout: () => u.post('/api/v1/auth/logout'),
  me: () => u.get('/api/v1/auth/me'),
}

export const guestApi = {
  create: (body) => u.post('/api/v1/guests/create', body),
  get: (guestId) => u.post('/api/v1/guests/get', { guest_id: guestId }),
  update: (body) => u.post('/api/v1/guests/update', body),
  remove: (guestId) => u.post('/api/v1/guests/delete', { guest_id: guestId }),
  search: (filters) => u.post('/api/v1/guests/search', filters),
}

export const hostApi = {
  create: (body) => u.post('/api/v1/hosts/create', body),
  get: (hostId) => u.post('/api/v1/hosts/get', { host_id: hostId }),
  update: (body) => u.post('/api/v1/hosts/update', body),
}

export function uploadProfilePhoto(file) {
  const form = new FormData()
  form.append('file', file)
  return u.post('/api/v1/users/profile-photo', form, { timeout: 30000 })
}

// profile_photo_url is relative to user-service; add a cache-buster after uploads.
export function photoSrc(url, version) {
  if (!url) return null
  return `${API_URLS.users}${url}${version ? `?v=${version}` : ''}`
}

export const AMENITIES = ['wifi', 'kitchen', 'parking', 'washer', 'air_conditioning', 'heating', 'pool',
  'pet_friendly', 'workspace', 'tv', 'hot_tub', 'ev_charger']
export const PROPERTY_TYPES = ['apartment', 'house', 'condo', 'cabin', 'private_room', 'shared_room']
export const label = (v) => v.replace(/_/g, ' ')
