import { useEffect, useState } from 'react'
import { API_URLS, getServiceHealth } from '../services/api.js'

// Shows whether the module's backend process answers GET /health.
export default function ServiceStatus({ serviceKey }) {
  const [state, setState] = useState({ status: 'checking' })

  useEffect(() => {
    let cancelled = false
    getServiceHealth(serviceKey)
      .then((data) => !cancelled && setState({ status: 'up', data }))
      .catch((err) => !cancelled && setState({ status: 'down', error: err.message }))
    return () => { cancelled = true }
  }, [serviceKey])

  return (
    <p className={`status status-${state.status}`} data-testid="service-status">
      Backend <code>{API_URLS[serviceKey]}</code>:{' '}
      {state.status === 'checking' && 'checking…'}
      {state.status === 'up' && 'running'}
      {state.status === 'down' && `not reachable (${state.error})`}
    </p>
  )
}
