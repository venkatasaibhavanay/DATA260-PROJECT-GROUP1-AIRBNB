import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import FormField, { ErrorBanner } from '../../components/FormField.jsx'
import { useAuth } from '../../context/AuthContext.jsx'
import { getErrorInfo } from '../../services/api.js'

export default function LoginPage() {
  const { user, signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [form, setForm] = useState({ email: '', password: '', role: 'guest' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to="/users" replace />

  const set = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await signIn(form.email, form.password, form.role)
      navigate(location.state?.from || '/users', { replace: true })
    } catch (err) {
      setError(getErrorInfo(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card narrow">
      <h1>Sign in</h1>
      <form onSubmit={submit} className="form">
        <div className="segmented" role="radiogroup" aria-label="Account type">
          {['guest', 'host', 'admin'].map((r) => (
            <button type="button" key={r} role="radio" aria-checked={form.role === r}
              className={form.role === r ? 'on' : ''} onClick={() => setForm({ ...form, role: r })}>
              {r[0].toUpperCase() + r.slice(1)}
            </button>
          ))}
        </div>
        <FormField label="Email" name="email" type="email" autoComplete="email" required
          value={form.email} onChange={set} />
        <FormField label="Password" name="password" type="password" autoComplete="current-password" required
          value={form.password} onChange={set} />
        <ErrorBanner info={error} />
        <button className="btn btn-primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
      </form>
      <p className="muted">New here? <Link to="/signup">Create an account</Link></p>
    </section>
  )
}
