import { moduleByKey } from '../services/modules.js'
import ServiceStatus from './ServiceStatus.jsx'

export default function ModulePlaceholder({ moduleKey, children }) {
  const m = moduleByKey(moduleKey)
  return (
    <section className="card">
      <h1>{m.name}</h1>
      <p className="owner">Owner: <strong>{m.owner}</strong> · Service: <code>{m.service}</code></p>
      <ServiceStatus serviceKey={m.key} />
      <div className="placeholder">
        <p>🚧 Development placeholder. Build this module's UI here.</p>
        {children}
      </div>
    </section>
  )
}
