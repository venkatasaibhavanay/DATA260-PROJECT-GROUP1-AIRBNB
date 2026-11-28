import { useEffect, useState } from 'react'
import FormField, { ErrorBanner } from '../../components/FormField.jsx'
import { getErrorInfo } from '../../services/api.js'
import { hostApi } from '../../services/users.js'
import PhotoUpload from './PhotoUpload.jsx'

// Own host profile (editable = true) or an admin managing any host (asAdmin = true).
export default function HostProfile({ hostId, editable = true, asAdmin = false }) {
  const [profile, setProfile] = useState(null)
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState(null)
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(false)
  const [busy, setBusy] = useState(false)

  const load = () => hostApi.get(hostId).then((res) => { setProfile(res.data); setError(null) })
    .catch((e) => { setProfile(null); setError(getErrorInfo(e)) })
  useEffect(() => { load() }, [hostId]) // eslint-disable-line react-hooks/exhaustive-deps

  function startEdit() {
    setForm({ name: profile.name, email: profile.email || '', phone: profile.phone || '',
      verification_status: profile.verification_status, access_level: profile.access_level })
    setEditing(true)
    setSaved(false)
    setError(null)
  }

  async function save(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    const body = { host_id: hostId, name: form.name, email: form.email, phone: form.phone.trim() || null }
    if (asAdmin) Object.assign(body, { verification_status: form.verification_status, access_level: form.access_level })
    try {
      await hostApi.update(body)
      await load()
      setEditing(false)
      setSaved(true)
    } catch (err) {
      setError(getErrorInfo(err))
    } finally {
      setBusy(false)
    }
  }

  if (!profile) return error ? <ErrorBanner info={error} /> : <p className="muted">Loading profile…</p>
  const set = (e) => setForm({ ...form, [e.target.name]: e.target.value })
  const fe = (k) => error?.fields?.[k]
  const rate = profile.response_rate == null ? '—' : `${Math.round(Number(profile.response_rate) * 100)}%`
  const time = profile.response_time_minutes == null ? '—'
    : profile.response_time_minutes < 60 ? `${profile.response_time_minutes} min`
      : `${(profile.response_time_minutes / 60).toFixed(1)} h`

  return (
    <div className="stack">
      <div className="profile-head">
        {editable && !asAdmin
          ? <PhotoUpload url={profile.profile_photo_url} name={profile.name}
              onUploaded={(url) => setProfile({ ...profile, profile_photo_url: url })} />
          : null}
        <div>
          <h2>{profile.name} <span className={`badge badge-${profile.verification_status}`}>{profile.verification_status}</span></h2>
          <p className="muted">Host since {profile.host_since}</p>
        </div>
      </div>

      <div className="stats">
        <div><strong>{rate}</strong><span>Response rate (30 days)</span></div>
        <div><strong>{time}</strong><span>Median response time</span></div>
      </div>

      {saved && <div className="alert alert-ok">Profile updated.</div>}

      {!editing ? (
        <>
          <dl className="details">
            <dt>Email</dt><dd>{profile.email || '—'}</dd>
            <dt>Phone</dt><dd>{profile.phone || '—'}</dd>
            <dt>Access level</dt><dd>{profile.access_level || '—'}</dd>
          </dl>
          {editable && <div className="actions"><button className="btn btn-primary" onClick={startEdit}>Edit profile</button></div>}
          <ErrorBanner info={error} />
        </>
      ) : (
        <form className="form" onSubmit={save} noValidate>
          <FormField label="Name" name="name" maxLength={120} value={form.name} onChange={set} error={fe('name')} />
          <FormField label="Email" name="email" type="email" value={form.email} onChange={set} error={fe('email')} />
          <FormField label="Phone" name="phone" type="tel" placeholder="+14085550101" value={form.phone} onChange={set} error={fe('phone')} />
          {asAdmin && (
            <div className="row">
              <FormField label="Verification" error={fe('verification_status')}>
                <select name="verification_status" value={form.verification_status} onChange={set}>
                  {['unverified', 'pending', 'verified'].map((v) => <option key={v}>{v}</option>)}
                </select>
              </FormField>
              <FormField label="Access level" error={fe('access_level')}>
                <select name="access_level" value={form.access_level} onChange={set}>
                  {['standard', 'superhost', 'suspended'].map((v) => <option key={v}>{v}</option>)}
                </select>
              </FormField>
            </div>
          )}
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
