import { Link } from 'react-router-dom'
import { MODULES } from '../services/modules.js'

export default function HomePage() {
  return (
    <section>
      <h1>Airbnb-Style Rental &amp; Booking Platform</h1>
      <p>DATA 260 Distributed Systems · Group 1 · San José State University</p>
      <div className="grid">
        {MODULES.map((m) => (
          <Link key={m.key} to={m.path} className="card tile">
            <h2>{m.name}</h2>
            <p>{m.owner}</p>
          </Link>
        ))}
      </div>
    </section>
  )
}
