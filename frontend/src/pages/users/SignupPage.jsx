import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import FormField, { ErrorBanner } from '../../components/FormField.jsx'
import { useAuth } from '../../context/AuthContext.jsx'
import { getErrorInfo } from '../../services/api.js'
import { guestApi, hostApi } from '../../services/users.js'
import PreferencesFields, { emptyPrefs, prefsToApi } from './PreferencesFields.jsx'

const blank = { first_name: '', last_name: '', name: '', email: '', password: '', phone: '', location: '' }

export default function SignupPage() {
  const { user, setSession } = useAuth()
  const navigate = useNavigate()
  const [role, setRole] = useState('guest')
  const [form, setForm] = useState(blank)
  const [prefs, setPrefs] = useState(emptyPrefs)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to="/users" replace />

  const set = (e) => setForm({ ...form, [e.target.name]: e.target.value })
  const fe = (k) => error?.fields?.[k]

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    const phone = form.phone.trim() || undefined
    try {
      if (role === 'guest') {
        const preferences = prefsToApi(prefs)
        const res = await guestApi.create({
          first_name: form.first_name, last_name: form.last_name, email: form.email, password: form.password,
          phone, location: form.location, ...(Object.keys(preferences).length ? { preferences } : {}),
        })
        const g = res.data.guest
        setSession(res.data.access_token, { id: g.guest_id, role: 'guest', name: `${g.first_name} ${g.last_name}`, email: g.email })
      } else {
        const res = await hostApi.create({ name: form.name, email: form.email, password: form.password, phone })
        const h = res.data.host
        setSession(res.data.access_token, { id: h.host_id, role: 'host', name: h.name, email: form.email.trim().toLowerCase() })
      }
      navigate('/users', { replace: true })
    } catch (err) {
      setError(getErrorInfo(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card narrow">
      <h1>Create an account</h1>
      <form onSubmit={submit} className="form" noValidate>
        <div className="segmented" role="radiogroup" aria-label="Account type">
          {[['guest', 'I want to travel'], ['host', 'I want to host']].map(([r, text]) => (
            <button type="button" key={r} role="radio" aria-checked={role === r}
              className={role === r ? 'on' : ''} onClick={() => { setRole(r); setError(null) }}>{text}</button>
          ))}
        </div>

        {role === 'guest' ? (
          <div className="row">
            <FormField label="First name" name="first_name" maxLength={60} required autoComplete="given-name"
              value={form.first_name} onChange={set} error={fe('first_name')} />
            <FormField label="Last name" name="last_name" maxLength={60} required autoComplete="family-name"
              value={form.last_name} onChange={set} error={fe('last_name')} />
          </div>
        ) : (
          <FormField label="Name" name="name" maxLength={120} required autoComplete="name"
            value={form.name} onChange={set} error={fe('name')} />
        )}
        <FormField label="Email" name="email" type="email" required autoComplete="email"
          value={form.email} onChange={set} error={fe('email')} />
        <FormField label="Password" name="password" type="password" required autoComplete="new-password"
          hint="At least 8 characters with a letter and a digit" value={form.password} onChange={set} error={fe('password')} />
        <FormField label="Phone (optional)" name="phone" type="tel" placeholder="+14085550101" autoComplete="tel"
          hint="International format, starting with +" value={form.phone} onChange={set} error={fe('phone')} />
        {role === 'guest' && (
          <>
            <FormField label="Location" name="location" required placeholder="San Jose, CA" maxLength={120}
              value={form.location} onChange={set} error={fe('location')} />
            <PreferencesFields value={prefs} onChange={setPrefs} errors={error?.fields || {}} />
          </>
        )}
        <ErrorBanner info={error} />
        <button className="btn btn-primary" disabled={busy}>{busy ? 'Creating account…' : 'Create account'}</button>
      </form>
      <p className="muted">Already have an account? <Link to="/login">Sign in</Link></p>
    </section>
  )
}
