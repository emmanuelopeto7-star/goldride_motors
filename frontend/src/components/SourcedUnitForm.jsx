import { useState } from 'react'
import { formatPrice } from '../lib/format'
import { errorMessages } from '../lib/errors'
import { landedCost } from '../lib/landedCost'

const fieldClass =
  'h-12 w-full border border-line bg-surface px-4 text-model outline-none focus:border-ink'
const labelClass = 'text-badge uppercase text-ink-soft'

function Field({ id, label, hint, ...props }) {
  return (
    <div>
      <label htmlFor={id} className={labelClass}>{label}</label>
      <input id={id} className={`mt-2 ${fieldClass}`} {...props} />
      {hint && <p className="mt-2 text-meta text-ink-mute">{hint}</p>}
    </div>
  )
}

/** Adding a unit against a request, with the total appearing as it is typed.
 *
 *  The running total is the point. Sourcing is a negotiation against a
 *  customer's budget, and knowing whether a unit lands over it only after
 *  saving turns every quote into guesswork. Figures here are a preview
 *  computed in the browser; once saved, everything on screen comes from the
 *  server instead.
 */
function SourcedUnitForm({ request, rates, mutation, onDone, unit = null }) {
  // Editing seeds from the saved unit, including the rates pinned to it -
  // reloading today's rates into an old quote would re-price it, which is the
  // exact thing pinning them was meant to prevent.
  const [values, setValues] = useState(() => ({
    make: unit?.make ?? request.make,
    model: unit?.model ?? request.model,
    year: unit?.year ?? request.year,
    chassis_number: unit?.chassis_number ?? '',
    mileage_km: unit?.mileage_km ?? '',
    grade: unit?.grade ?? '',
    exterior_colour: unit?.exterior_colour ?? '',
    auction_sheet_url: unit?.auction_sheet_url ?? '',
    unit_price_usd: unit?.unit_price_usd ?? '',
    freight_usd: unit?.freight_usd ?? '',
    insurance_usd: unit?.insurance_usd ?? '',
    dollar_rate: unit?.dollar_rate ?? '',
    excise_rate: unit?.excise_rate ?? rates?.excise_default ?? '',
    customs_value_kes: unit?.customs_value_kes ?? '',
    clearing_kes: unit?.clearing_kes ?? '',
    service_fee_kes: unit?.service_fee_kes ?? '',
  }))

  function set(field) {
    return (event) =>
      setValues((current) => ({ ...current, [field]: event.target.value }))
  }

  const preview = landedCost(values, rates)
  const budget = Number(request.budget_kes) || 0
  const overBudget = budget > 0 && preview && preview.total > budget

  function handleSubmit(event) {
    event.preventDefault()
    // Blank numerics must go up as null, not "" - DRF rejects the empty string
    // for a decimal field and the error lands on a field nobody filled in.
    const payload = Object.fromEntries(
      Object.entries(values).map(([key, value]) => [key, value === '' ? null : value]),
    )
    mutation.mutate(unit ? { ...payload, unitId: unit.id } : payload, {
      onSuccess: onDone,
    })
  }

  const rows = preview
    ? [
        ['Cost and freight', preview.cnfKes],
        ['Cost, insurance and freight', preview.cifKes],
        ['Import duty', preview.duty],
        ['Excise duty', preview.excise],
        ['VAT', preview.vat],
        ['IDF', preview.idf],
        ['Railway development levy', preview.rdl],
        ['Port and clearing', preview.clearing],
        ['Landed cost', preview.landed],
        ['Our fee', preview.fee],
      ]
    : []

  return (
    <form onSubmit={handleSubmit} className="grid gap-12 lg:grid-cols-[1fr_360px]">
      <div>
        <fieldset>
          <legend className={labelClass}>The vehicle</legend>
          <div className="mt-4 grid gap-6 sm:grid-cols-2">
            <Field id="u-make" label="Make" required value={values.make} onChange={set('make')} />
            <Field id="u-model" label="Model" required value={values.model} onChange={set('model')} />
            <Field id="u-year" label="Year" type="number" required value={values.year} onChange={set('year')} />
            <Field id="u-chassis" label="Chassis number" value={values.chassis_number} onChange={set('chassis_number')} placeholder="TRJ150-0012345" />
            <Field id="u-mileage" label="Mileage (km)" type="number" min="0" value={values.mileage_km} onChange={set('mileage_km')} />
            <Field id="u-grade" label="Auction grade" value={values.grade} onChange={set('grade')} placeholder="4.5" />
            <Field id="u-colour" label="Colour" value={values.exterior_colour} onChange={set('exterior_colour')} />
            <Field id="u-sheet" label="Auction sheet URL" type="url" value={values.auction_sheet_url} onChange={set('auction_sheet_url')} />
          </div>
        </fieldset>

        <fieldset className="mt-12 border-t border-line pt-12">
          <legend className={labelClass}>The quote</legend>
          <div className="mt-4 grid gap-6 sm:grid-cols-2">
            <Field id="u-price" label="Unit price (USD)" type="number" step="0.01" required value={values.unit_price_usd} onChange={set('unit_price_usd')} />
            <Field id="u-rate" label="Dollar rate (KES)" type="number" step="0.01" required value={values.dollar_rate} onChange={set('dollar_rate')} hint="Pinned to this quote — it will not move later." />
            <Field id="u-freight" label="Freight (USD)" type="number" step="0.01" value={values.freight_usd} onChange={set('freight_usd')} />
            <Field id="u-insurance" label="Insurance (USD)" type="number" step="0.01" value={values.insurance_usd} onChange={set('insurance_usd')} />
            <Field id="u-excise" label="Excise rate (%)" type="number" step="0.01" value={values.excise_rate} onChange={set('excise_rate')} hint="Banded by engine capacity." />
            <Field id="u-customs" label="KRA customs value (KES)" type="number" step="0.01" value={values.customs_value_kes} onChange={set('customs_value_kes')} hint="Leave blank to assess on CIF." />
            <Field id="u-clearing" label="Port and clearing (KES)" type="number" step="0.01" value={values.clearing_kes} onChange={set('clearing_kes')} />
            <Field id="u-fee" label="Our fee (KES)" type="number" step="0.01" value={values.service_fee_kes} onChange={set('service_fee_kes')} />
          </div>
        </fieldset>

        {mutation.isError && (
          <ul className="mt-8">
            {errorMessages(mutation.error).map((message) => (
              <li key={message} className="text-meta text-ink">{message}</li>
            ))}
          </ul>
        )}
      </div>

      <aside className="h-fit border border-line bg-surface p-6 lg:sticky lg:top-28">
        <p className={labelClass}>What the customer pays</p>
        <p className="mt-2 text-price">
          {preview ? formatPrice(preview.total) : '—'}
        </p>

        {overBudget && (
          <p className="mt-3 border border-ink p-3 text-meta leading-relaxed">
            Over the {formatPrice(budget)} budget they gave by{' '}
            {formatPrice(preview.total - budget)}.
          </p>
        )}

        <dl className="mt-6 border-t border-line pt-4">
          {rows.map(([label, value]) => (
            <div
              key={label}
              className="flex justify-between gap-4 border-b border-line py-2 text-meta"
            >
              <dt className="text-ink-soft">{label}</dt>
              <dd>{formatPrice(value)}</dd>
            </div>
          ))}
        </dl>

        <p className="mt-4 text-meta text-ink-mute">
          Preview only. The saved figures come from the server.
        </p>

        <button
          type="submit"
          disabled={mutation.isPending}
          className="mt-6 h-12 w-full bg-ink text-badge uppercase text-surface disabled:opacity-50"
        >
          {mutation.isPending ? 'Saving...' : unit ? 'Save changes' : 'Add this unit'}
        </button>
      </aside>
    </form>
  )
}

export default SourcedUnitForm
