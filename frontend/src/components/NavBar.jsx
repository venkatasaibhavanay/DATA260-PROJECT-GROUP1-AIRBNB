import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { MODULES } from '../services/modules.js'

export default function NavBar() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  return (
    <header className="navbar">
      <NavLink to="/" className="brand">Group 1 Airbnb</NavLink>
      <nav>
        {MODULES.map((m) => (
          <NavLink key={m.key} to={m.path} className={({ isActive }) => (isActive ? 'active' : '')}>
            {m.name}
          </NavLink>
        ))}
      </nav>
      <div className="nav-user">
        {user ? (
          <>
            <Link to="/users" className="nav-name">{user.name} <span className="muted">({user.role})</span></Link>
            <button className="btn btn-small" onClick={async () => { await signOut(); navigate('/') }}>Sign out</button>
          </>
        ) : (
          <Link to="/login" className="btn btn-small">Sign in</Link>
        )}
      </div>
    </header>
  )
}
