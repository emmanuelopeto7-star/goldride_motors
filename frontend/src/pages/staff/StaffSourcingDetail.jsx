import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import ErrorState from '../../components/ErrorState'
import SourcedUnitForm from '../../components/SourcedUnitForm'
import { errorMessages } from '../../lib/errors'
import { formatPrice } from '../../lib/format'
import { useImportRates, useImportRequestDetail } from '../../hooks/useSourcing'

const STATUS_LABEL = {
  pending: 'To source',
  sourcing: 'In progress',
  awaiting_selection: 'With customer',
  agreed: 'Agreed',
  cancelled: 'Cancelled',
}

function UnitRow({ unit, onPush, isPushing, onEdit }) {
  const spec = [
    unit.mileage_km && `${Number(unit.mileage_km).toLocaleString('en-KE')} km`,
    unit.grade && `Grade ${unit.grade}`,
    unit.exterior_colour,
    unit.chassis_number,
  ].filter(Boolean)

  return (
    <li className="border border-line bg-surface p-6">
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-model">
              {unit.year} {unit.make} {unit.model}
            </p>
            <span
              className={`rounded-full px-3 py-1 text-badge uppercase ${
                unit.status === 'selected'
                  ? 'bg-ink text-surface'
                  : 'border border-line text-ink-soft'
              }`}
            >
              {unit.status}
            </span>
          </div>
          {spec.length > 0 && (
            <p className="mt-1 text-meta text-ink-soft">{spec.join(' · ')}</p>
          )}
        </div>

        <dl className="flex flex-wrap gap-x-10 gap-y-3 text-meta">
          <div>
            <dt className="text-ink-soft">Cost to us</dt>
            <dd className="mt-1">{formatPrice(unit.landed_cost_kes)}</dd>
          </div>
          <div>
            <dt className="text-ink-soft">Quoted</dt>
            <dd className="mt-1">{formatPrice(unit.total_kes)}</dd>
          </div>
          <div>
            <dt className="text-ink-soft">At</dt>
            <dd className="mt-1">KES {unit.dollar_rate}</dd>
          </div>
        </dl>
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-4 border-t border-line pt-6">
        {/* Correcting a quote stays available at any status - a mistyped
            dollar rate is worth fixing even on a unit already declined. */}
        <button
          type="button"
          onClick={() => onEdit(unit)}
          className="text-meta text-ink underline"
        >
          Edit this quote
        </button>

        {/* Only a unit nobody took, and only once. The API refuses otherwise. */}
        {unit.status === 'rejected' && !unit.pushed_to_car && (
          <>
            <button
              type="button"
              disabled={isPushing}
              onClick={() => onPush(unit)}
              className="h-11 border border-ink px-6 text-badge uppercase disabled:opacity-50"
            >
              Push to stock
            </button>
            <p className="text-meta text-ink-soft">
              Would list at {formatPrice(unit.stock_price_preview)}
            </p>
          </>
        )}
      </div>

      {unit.pushed_to_car && (
        <p className="mt-6 border-t border-line pt-6 text-meta text-ink-soft">
          Listed as{' '}
          <Link to={`/cars/${unit.pushed_to_car}`} className="text-ink underline">
            car #{unit.pushed_to_car}
          </Link>
          .
        </p>
      )}
    </li>
  )
}

function StaffSourcingDetail() {
  const { id } = useParams()
  const { query, addUnit, updateUnit, notify, pushToStock } =
    useImportRequestDetail(id)
  const { data: rates } = useImportRates()
  const [adding, setAdding] = useState(false)
  const [editingUnit, setEditingUnit] = useState(null)

  if (query.isPending) {
    return <div className="h-64 w-full animate-pulse bg-line" />
  }

  if (query.isError) {
    return (
      <ErrorState message="We could not load this request." onRetry={query.refetch} />
    )
  }

  const request = query.data
  const units = request.units ?? []
  const offered = units.filter((unit) => unit.status === 'offered').length

  return (
    <div>
      <Link to="/staff/sourcing" className="text-meta text-ink underline">
        ← All requests
      </Link>

      <div className="mt-6 flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
        <div>
          <h2 className="font-serif text-section">
            {request.year} {request.make} {request.model}
          </h2>
          <p className="mt-1 text-meta text-ink-soft">
            {request.contact_name} · {request.phone} · {request.email}
          </p>
        </div>
        <span className="rounded-full border border-line px-3 py-1 text-badge uppercase text-ink-soft">
          {STATUS_LABEL[request.status] ?? request.status}
        </span>
      </div>

      <dl className="mt-6 flex flex-wrap gap-x-12 gap-y-4 border-y border-line py-6 text-meta">
        <div>
          <dt className="text-ink-soft">Budget</dt>
          <dd className="mt-1">
            {request.budget_kes ? formatPrice(request.budget_kes) : 'Not stated'}
          </dd>
        </div>
        <div>
          <dt className="text-ink-soft">Asked</dt>
          <dd className="mt-1">
            {new Date(request.created_at).toLocaleDateString('en-KE')}
          </dd>
        </div>
        <div>
          <dt className="text-ink-soft">Their link</dt>
          <dd className="mt-1">
            <a
              href={`/imports/${request.token}`}
              target="_blank"
              rel="noreferrer"
              className="text-ink underline"
            >
              What the customer sees
            </a>
          </dd>
        </div>
      </dl>

      {request.notes && (
        <p className="mt-6 max-w-[68ch] text-model leading-relaxed text-ink-soft">
          {request.notes}
        </p>
      )}

      <section className="mt-12">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h3 className="font-serif text-section">
            {units.length === 0 ? 'No units yet' : `${units.length} sourced`}
          </h3>

          {/* Nothing to tell them about until something is on offer, and the
              API refuses an empty notify anyway. */}
          {offered > 0 && (
            <button
              type="button"
              disabled={notify.isPending}
              onClick={() => notify.mutate()}
              className="h-11 bg-ink px-6 text-badge uppercase text-surface disabled:opacity-50"
            >
              {notify.isPending
                ? 'Sending...'
                : request.status === 'awaiting_selection'
                  ? 'Send again'
                  : `Tell them about ${offered}`}
            </button>
          )}
        </div>

        {notify.isSuccess && (
          <p className="mt-4 border border-line bg-surface p-4 text-meta text-ink-soft">
            Emailed {request.email}. They can now choose from their link.
          </p>
        )}

        {(notify.isError || pushToStock.isError) && (
          <ul className="mt-4">
            {errorMessages(notify.error ?? pushToStock.error).map((message) => (
              <li key={message} className="text-meta text-ink">{message}</li>
            ))}
          </ul>
        )}

        {units.length > 0 && (
          <ul className="mt-6 space-y-4">
            {units.map((unit) => (
              <UnitRow
                key={unit.id}
                unit={unit}
                isPushing={pushToStock.isPending}
                onPush={(target) => pushToStock.mutate({ unitId: target.id })}
                onEdit={(target) => {
                  updateUnit.reset()
                  setEditingUnit(target)
                  setAdding(false)
                }}
              />
            ))}
          </ul>
        )}
      </section>

      {editingUnit && (
        <section className="mt-16 border-t border-line pt-12">
          <h3 className="font-serif text-section">
            Edit {editingUnit.year} {editingUnit.make} {editingUnit.model}
          </h3>
          <div className="mt-8">
            <SourcedUnitForm
              request={request}
              rates={rates}
              unit={editingUnit}
              mutation={updateUnit}
              onDone={() => setEditingUnit(null)}
            />
          </div>
          <button
            type="button"
            onClick={() => setEditingUnit(null)}
            className="mt-6 text-meta text-ink underline"
          >
            Cancel
          </button>
        </section>
      )}

      <section className="mt-16 border-t border-line pt-12">
        {adding ? (
          <>
            <h3 className="font-serif text-section">Add a unit</h3>
            <div className="mt-8">
              <SourcedUnitForm
                request={request}
                rates={rates}
                mutation={addUnit}
                onDone={() => setAdding(false)}
              />
            </div>
          </>
        ) : (
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="h-12 border border-ink px-8 text-badge uppercase"
          >
            Add a sourced unit
          </button>
        )}
      </section>
    </div>
  )
}

export default StaffSourcingDetail
