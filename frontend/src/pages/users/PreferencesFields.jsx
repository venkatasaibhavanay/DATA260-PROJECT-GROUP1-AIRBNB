import FormField from '../../components/FormField.jsx'
import { AMENITIES, PROPERTY_TYPES, label } from '../../services/users.js'

// Controlled editor for guest preferences. value uses form-friendly shapes:
// { preferred_locations: 'San Jose, Austin', budget_max: '250.00', amenities: [], property_types: [], travel_purpose: '' }
export const emptyPrefs = { preferred_locations: '', budget_max: '', amenities: [], property_types: [], travel_purpose: '' }

export function prefsFromApi(p = {}) {
  return {
    preferred_locations: (p.preferred_locations || []).join(', '),
    budget_max: p.budget_max || '',
    amenities: p.amenities || [],
    property_types: p.property_types || [],
    travel_purpose: p.travel_purpose || '',
  }
}

export function prefsToApi(v) {
  const out = {}
  const locs = v.preferred_locations.split(',').map((s) => s.trim()).filter(Boolean)
  if (locs.length) out.preferred_locations = [...new Set(locs)]
  if (v.budget_max !== '') out.budget_max = v.budget_max
  if (v.amenities.length) out.amenities = v.amenities
  if (v.property_types.length) out.property_types = v.property_types
  if (v.travel_purpose.trim()) out.travel_purpose = v.travel_purpose.trim()
  return out
}

function Chips({ options, selected, onChange }) {
  const toggle = (o) => onChange(selected.includes(o) ? selected.filter((x) => x !== o) : [...selected, o])
  return (
    <div className="chips">
      {options.map((o) => (
        <button type="button" key={o} className={selected.includes(o) ? 'chip on' : 'chip'}
          aria-pressed={selected.includes(o)} onClick={() => toggle(o)}>{label(o)}</button>
      ))}
    </div>
  )
}

export default function PreferencesFields({ value, onChange, errors = {} }) {
  const set = (k) => (e) => onChange({ ...value, [k]: e.target ? e.target.value : e })
  const err = (k) => Object.entries(errors).find(([f]) => f.startsWith(`preferences.${k}`))?.[1]
  return (
    <fieldset className="fieldset">
      <legend>Travel preferences <span className="muted">(optional)</span></legend>
      <FormField label="Preferred locations" hint="Comma-separated, e.g. San Jose, Austin"
        value={value.preferred_locations} onChange={set('preferred_locations')} error={err('preferred_locations')} />
      <FormField label="Max nightly budget (USD)" inputMode="decimal" placeholder="250.00"
        value={value.budget_max} onChange={set('budget_max')} error={err('budget_max')} />
      <FormField label="Amenities" error={err('amenities')}>
        <Chips options={AMENITIES} selected={value.amenities} onChange={set('amenities')} />
      </FormField>
      <FormField label="Property types" error={err('property_types')}>
        <Chips options={PROPERTY_TYPES} selected={value.property_types} onChange={set('property_types')} />
      </FormField>
      <FormField label="Travel purpose" placeholder="business, family, …" maxLength={40}
        value={value.travel_purpose} onChange={set('travel_purpose')} error={err('travel_purpose')} />
    </fieldset>
  )
}
