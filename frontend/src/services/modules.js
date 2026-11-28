// One entry per vertical slice. Drives the navbar, home page, and placeholders.
export const MODULES = [
  { key: 'users', path: '/users', name: 'User & Host Profiles', owner: 'Nathan Pak', service: 'user-service' },
  { key: 'properties', path: '/properties', name: 'Property & Search', owner: 'Sanjana Reddy Katham', service: 'property-service' },
  { key: 'bookings', path: '/bookings', name: 'Booking & Reservations', owner: 'Venkata Sai Bhavana Yarrapragada', service: 'booking-service' },
  { key: 'messaging', path: '/messaging-reviews', name: 'Messaging & Reviews', owner: 'Srija Taduri', service: 'messaging-review-service' },
  { key: 'ai', path: '/ai', name: 'Agentic AI & Recommendations', owner: 'Angela Wai', service: 'ai-service' },
  { key: 'analytics', path: '/analytics', name: 'Analytics & Observability', owner: 'Eric Zhao', service: 'analytics-service' },
]

export const moduleByKey = (key) => MODULES.find((m) => m.key === key)
