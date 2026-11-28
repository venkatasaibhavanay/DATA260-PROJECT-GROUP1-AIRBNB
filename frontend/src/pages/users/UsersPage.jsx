import { useState } from 'react'
import { Link } from 'react-router-dom'
import ServiceStatus from '../../components/ServiceStatus.jsx'
import { useAuth } from '../../context/AuthContext.jsx'
import GuestProfile from './GuestProfile.jsx'
import GuestSearch from './GuestSearch.jsx'
import HostProfile from './HostProfile.jsx'

function AdminHostLookup() {
  const [input, setInput] = useState('')
  const [hostId, setHostId] = useState(null)
  return (
    <div className="stack">
      <form className="search" onSubmit={(e) => { e.preventDefault(); setHostId(Number(input) || null) }}>
        <input placeholder="Host ID, e.g. 501" aria-label="Host ID" inputMode="numeric" value={input}
          onChange={(e) => setInput(e.target.value)} />
        <button className="btn btn-primary">Open host</button>
      </form>
      {hostId && <HostProfile key={hostId} hostId={hostId} asAdmin />}
    </div>
  )
}

export default function UsersPage() {
  const { user, loading } = useAuth()

  if (loading) return <p className="muted">Loading…</p>

  if (!user) {
    return (
      <section className="card">
        <h1>User &amp; Host Profiles</h1>
        <ServiceStatus serviceKey="users" />
        <p>Sign in to see your profile, or create a guest or host account.</p>
        <div className="actions">
          <Link className="btn btn-primary" to="/login">Sign in</Link>
          <Link className="btn" to="/signup">Create an account</Link>
        </div>
      </section>
    )
  }

  return (
    <section className="stack">
      <div className="card">
        <h1>{user.role === 'admin' ? 'Admin' : 'Your profile'}</h1>
        {user.role === 'guest' && <GuestProfile guestId={user.id} />}
        {user.role === 'host' && <HostProfile hostId={user.id} />}
        {user.role === 'admin' && <p className="muted">Signed in as {user.email}.</p>}
      </div>
      {(user.role === 'host' || user.role === 'admin') && (
        <div className="card">
          <h2>Find guests</h2>
          <GuestSearch />
        </div>
      )}
      {user.role === 'admin' && (
        <div className="card">
          <h2>Manage a host</h2>
          <AdminHostLookup />
        </div>
      )}
    </section>
  )
}
