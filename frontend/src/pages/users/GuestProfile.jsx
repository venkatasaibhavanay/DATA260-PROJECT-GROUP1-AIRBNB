import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import FormField, { ErrorBanner } from '../../components/FormField.jsx'
import { useAuth } from '../../context/AuthContext.jsx'
import { getErrorInfo } from '../../services/api.js'
import { guestApi, label } from '../../services/users.js'
import PhotoUpload from './PhotoUpload.jsx'
import PreferencesFields, { prefsFromApi, prefsToApi } from './PreferencesFields.jsx'

const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString() : '')

export default function GuestProfile({ guestId }) {
  const { forget } = useAuth()
  const navigate = useNavigate()
  const [profile, setProfile] = useState(null)
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState(null)
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(false)
  const [busy, setBusy] = useState(false)

  const load = () => guestApi.get(guestId).then((res) => setProfile(res.data)).catch((e) => setError(getErrorInfo(e)))
  useEffect(() => { load() }, [guestId]) // eslint-disable-line react-hooks/exhaustive-deps

  function startEdit() {
    setForm({ first_name: profile.first_name, last_name: profile.last_name, email: profile.email,
      phone: profile.phone || '', location: profile.location, prefs: prefsFromApi(profile.preferences) })
    setEditing(true)
    setSaved(false)
    setError(null)
  }

  async function save(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await guestApi.update({
        guest_id: guestId, first_name: form.first_name, last_name: form.last_name, email: form.email,
        phone: form.phone.trim() || null, location: form.location, preferences: prefsToApi(form.prefs),
      })
      await load()
      setEditing(false)
      setSaved(true)
    } catch (err) {
      setError(getErrorInfo(err))
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    if (!window.confirm('Delete your guest profile? Your reservations will be cancelled and you will be signed out. This cannot be undone.')) return
    setBusy(true)
    try {
      await guestApi.remove(guestId)
      forget()
      navigate('/', { replace: true })
    } catch (err) {
      setError(getErrorInfo(err))
      setBusy(false)
    }
  }

  if (!profile) return error ? <ErrorBanner info={error} /> : <p className="muted">Loading profile…</p>
  const set = (e) => setForm({ ...form, [e.target.name]: e.target.value })
  const fe = (k) => error?.fields?.[k]
  const p = profile.preferences || {}

  return (
    <div className="stack">
      <div className="profile-head">
        <PhotoUpload url={profile.profile_photo_url} name={`${profile.first_name} ${profile.last_name}`}
          onUploaded={(url) => setProfile({ ...profile, profile_photo_url: url })} />
        <div>
          <h2>{profile.first_name} {profile.last_name}</h2>
          <p className="muted">Guest since {fmtDate(profile.profile_created_datetime)}</p>
        </div>
      </div>

      <div className="stats">
        <div><strong>{profile.saved_properties_count}</strong><span>Saved properties</span></div>
        <div><strong>{profile.booking_count}</strong><span>Bookings</span></div>
      </div>

      {saved && <div className="alert alert-ok">Profile updated.</div>}

      {!editing ? (
        <>
          <dl className="details">
            <dt>Email</dt><dd>{profile.email}</dd>
            <dt>Phone</dt><dd>{profile.phone || '—'}</dd>
            <dt>Location</dt><dd>{profile.location}</dd>
            <dt>Preferred locations</dt><dd>{p.preferred_locations?.join(', ') || '—'}</dd>
            <dt>Max budget</dt><dd>{p.budget_max ? `$${p.budget_max} / night` : '—'}</dd>
            <dt>Amenities</dt><dd>{p.amenities?.map(label).join(', ') || '—'}</dd>
            <dt>Property types</dt><dd>{p.property_types?.map(label).join(', ') || '—'}</dd>
            <dt>Travel purpose</dt><dd>{p.travel_purpose || '—'}</dd>
          </dl>
          <div className="actions">
            <button className="btn btn-primary" onClick={startEdit}>Edit profile</button>
            <button className="btn btn-danger" onClick={remove} disabled={busy}>Delete profile</button>
          </div>
          <ErrorBanner info={error} />
        </>
      ) : (
        <form className="form" onSubmit={save} noValidate>
          <div className="row">
            <FormField label="First name" name="first_name" maxLength={60} value={form.first_name} onChange={set} error={fe('first_name')} />
            <FormField label="Last name" name="last_name" maxLength={60} value={form.last_name} onChange={set} error={fe('last_name')} />
          </div>
          <FormField label="Email" name="email" type="email" value={form.email} onChange={set} error={fe('email')} />
          <FormField label="Phone" name="phone" type="tel" placeholder="+14085550101" value={form.phone} onChange={set} error={fe('phone')} />
          <FormField label="Location" name="location" maxLength={120} value={form.location} onChange={set} error={fe('location')} />
          <PreferencesFields value={form.prefs} onChange={(prefs) => setForm({ ...form, prefs })} errors={error?.fields || {}} />
          <ErrorBanner info={error} />
          <div className="actions">
            <button className="btn btn-primary" disabled={busy}>{busy ? 'Saving…' : 'Save changes'}</button>
            <button type="button" className="btn" onClick={() => { setEditing(false); setError(null) }}>Cancel</button>
          </div>
        </form>
      )}
    </div>
  )
}
