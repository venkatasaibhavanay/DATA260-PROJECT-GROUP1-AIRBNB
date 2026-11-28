import { useState } from 'react'
import { ErrorBanner } from '../../components/FormField.jsx'
import { getErrorInfo } from '../../services/api.js'
import { guestApi, photoSrc } from '../../services/users.js'

// Host/admin guest search (POST /guests/search). Admins also see email.
export default function GuestSearch() {
  const [filters, setFilters] = useState({ q: '', location: '' })
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function run(page = 1) {
    setBusy(true)
    setError(null)
    try {
      const res = await guestApi.search({ q: filters.q || undefined, location: filters.location || undefined, page, page_size: 10 })
      setResult(res.data)
    } catch (err) {
      setError(getErrorInfo(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stack">
      <form className="search" onSubmit={(e) => { e.preventDefault(); run(1) }}>
        <input placeholder="Name" aria-label="Guest name" value={filters.q}
          onChange={(e) => setFilters({ ...filters, q: e.target.value })} />
        <input placeholder="Location" aria-label="Guest location" value={filters.location}
          onChange={(e) => setFilters({ ...filters, location: e.target.value })} />
        <button className="btn btn-primary" disabled={busy}>Search</button>
      </form>
      <ErrorBanner info={error} />
      {result && (
        <>
          <p className="muted">{result.total} guest{result.total === 1 ? '' : 's'} found</p>
          <ul className="people">
            {result.items.map((g) => (
              <li key={g.guest_id}>
                {g.profile_photo_url ? <img className="avatar sm" src={photoSrc(g.profile_photo_url)} alt="" />
                  : <span className="avatar sm avatar-empty">{g.first_name[0]}</span>}
                <div>
                  <strong>{g.first_name} {g.last_name}</strong>
                  <span className="muted"> · {g.location}{g.email ? ` · ${g.email}` : ''}</span>
                </div>
                <code className="muted">#{g.guest_id}</code>
              </li>
            ))}
          </ul>
          {result.total_pages > 1 && (
            <div className="actions">
              <button className="btn" disabled={busy || result.page <= 1} onClick={() => run(result.page - 1)}>Previous</button>
              <span className="muted">Page {result.page} of {result.total_pages}</span>
              <button className="btn" disabled={busy || result.page >= result.total_pages} onClick={() => run(result.page + 1)}>Next</button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
