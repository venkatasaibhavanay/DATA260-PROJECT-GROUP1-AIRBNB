// Label + input + server-side field error (from getErrorInfo(err).fields).
const clean = (msg) => String(msg).replace(/^Value error, /, '')

export default function FormField({ label, name, error, hint, children, ...inputProps }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children || <input name={name} aria-invalid={Boolean(error)} {...inputProps} />}
      {hint && !error && <span className="field-hint">{hint}</span>}
      {error && <span className="field-error">{clean(error)}</span>}
    </label>
  )
}

export function ErrorBanner({ info }) {
  if (!info) return null
  return (
    <div className="alert alert-error" role="alert">
      {info.message}
      {info.traceId && <small className="trace"> · trace {info.traceId.slice(0, 8)}</small>}
    </div>
  )
}
