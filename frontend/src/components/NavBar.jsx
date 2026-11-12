import { NavLink } from 'react-router-dom'
import { MODULES } from '../services/modules.js'

export default function NavBar() {
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
    </header>
  )
}
