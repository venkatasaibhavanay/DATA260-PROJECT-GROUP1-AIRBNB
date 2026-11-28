import { useRef, useState } from 'react'
import { ErrorBanner } from '../../components/FormField.jsx'
import { getErrorInfo } from '../../services/api.js'
import { photoSrc, uploadProfilePhoto } from '../../services/users.js'

const MAX = 5 * 1024 * 1024

export default function PhotoUpload({ url, name, onUploaded }) {
  const input = useRef(null)
  const [version, setVersion] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function pick(e) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    if (!['image/jpeg', 'image/png'].includes(file.type)) return setError({ message: 'Choose a JPEG or PNG image.' })
    if (file.size > MAX) return setError({ message: 'Photo must be 5 MB or smaller.' })
    setBusy(true)
    setError(null)
    try {
      const res = await uploadProfilePhoto(file)
      setVersion(Date.now())
      onUploaded?.(res.data.profile_photo_url)
    } catch (err) {
      setError(getErrorInfo(err))
    } finally {
      setBusy(false)
    }
  }

  const initials = (name || '?').split(' ').map((p) => p[0]).join('').slice(0, 2).toUpperCase()
  return (
    <div className="photo">
      {url ? <img className="avatar" src={photoSrc(url, version)} alt={`${name} profile`} />
        : <div className="avatar avatar-empty" aria-hidden="true">{initials}</div>}
      <div>
        <button type="button" className="btn" disabled={busy} onClick={() => input.current.click()}>
          {busy ? 'Uploading…' : url ? 'Change photo' : 'Add photo'}
        </button>
        <p className="field-hint">JPEG or PNG, up to 5 MB</p>
        <input ref={input} type="file" accept="image/jpeg,image/png" hidden onChange={pick} />
        <ErrorBanner info={error} />
      </div>
    </div>
  )
}
