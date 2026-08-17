import { useState } from 'react'
import { formatPrice } from '../lib/format'

/** One unit we found, with the arithmetic behind its price.
 *
 *  The breakdown is not decoration. Someone comparing importers is comparing
 *  tax arithmetic, and a single "duties" figure is the one line they cannot
 *  check — so every KRA charge is listed separately, in the order it is
 *  actually applied.
 */
function SourcedUnitCard({ unit, onDecide, isDeciding, decided }) {
  const [open, setOpen] = useState(false)

  const spec = [
    unit.mileage_km && `${unit.mileage_km.toLocaleString('en-KE')} km`,
    unit.grade && `Grade ${unit.grade}`,
    unit.exterior_colour,
    unit.chassis_number,
  ].filter(Boolean)

  const charges = [
    // CIF, because that is what every charge below is assessed on - and
    // because with C&F the lines come up short of the total by the insurance.
    ['Cost, insurance and freight', unit.cif_kes],
    ['Import duty', unit.import_duty_kes],
    ['Excise duty', unit.excise_duty_kes],
    ['VAT', unit.vat_kes],
    ['IDF', unit.idf_kes],
    ['Railway development levy', unit.rdl_kes],
    ['Port and clearing', unit.clearing_kes],
    ['Our fee', unit.service_fee_kes],
  ]

  const selected = unit.status === 'selected'
  const rejected = unit.status === 'rejected'

  return (
    <article
      className={`border bg-surface p-6 lg:p-8 ${
        selected ? 'border-ink' : 'border-line'
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="font-serif text-section">
              {unit.year} {unit.make} {unit.model}
            </h3>
            {selected && (
              <span className="rounded-full bg-ink px-3 py-1 text-badge uppercase text-surface">
                Chosen
              </span>
            )}
            {rejected && (
              <span className="rounded-full border border-line px-3 py-1 text-badge uppercase text-ink-soft">
                Declined
              </span>
            )}
          </div>
          {spec.length > 0 && (
            <p className="mt-2 text-meta text-ink-soft">{spec.join(' · ')}</p>
          )}
        </div>

        <div className="text-right">
          <p className="text-price">{formatPrice(unit.total_kes)}</p>
          <p className="mt-1 text-meta text-ink-soft">Delivered and cleared</p>
        </div>
      </div>

      {unit.photo && (
        <img
          src={unit.photo}
          alt={`${unit.year} ${unit.make} ${unit.model}`}
          loading="lazy"
          className="mt-6 aspect-[4/3] w-full max-w-[420px] object-cover"
        />
      )}

      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="mt-6 text-meta text-ink underline"
      >
        {open ? 'Hide the breakdown' : 'See how this is worked out'}
      </button>

      {open && (
        <dl className="mt-4 max-w-[420px]">
          {charges.map(([label, value]) => (
            <div
              key={label}
              className="flex justify-between gap-8 border-b border-line py-2 text-meta"
            >
              <dt className="text-ink-soft">{label}</dt>
              <dd>{formatPrice(value)}</dd>
            </div>
          ))}
          <div className="flex justify-between gap-8 py-3 text-model">
            <dt>Total</dt>
            <dd>{formatPrice(unit.total_kes)}</dd>
          </div>
          <p className="text-meta text-ink-soft">
            Quoted at KES {unit.dollar_rate} to the dollar. Duties are assessed
            by KRA on arrival and can move if that rate does.
          </p>
        </dl>
      )}

      {unit.rejected_reason && (
        <p className="mt-6 border-t border-line pt-6 text-meta text-ink-soft">
          {unit.rejected_reason}
        </p>
      )}

      {/* Only an unresolved unit can be decided, and only while nothing else
          has been chosen — the API refuses otherwise, so offering the buttons
          would be a promise the server breaks. */}
      {unit.status === 'offered' && !decided && (
        <div className="mt-8 flex flex-wrap gap-3 border-t border-line pt-8">
          <button
            type="button"
            disabled={isDeciding}
            onClick={() => onDecide(unit, 'select')}
            className="h-12 bg-ink px-8 text-badge uppercase text-surface disabled:opacity-50"
          >
            Choose this one
          </button>
          <button
            type="button"
            disabled={isDeciding}
            onClick={() => onDecide(unit, 'reject')}
            className="h-12 border border-ink px-8 text-badge uppercase disabled:opacity-50"
          >
            Not this one
          </button>
        </div>
      )}
    </article>
  )
}

export default SourcedUnitCard
