import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import CarEditModal from '../../components/CarEditModal'
import EmptyState from '../../components/EmptyState'
import Pagination from '../../components/Pagination'
import ErrorState from '../../components/ErrorState'
import { formatPrice } from '../../lib/format'
import {
  EXPIRING_SOON_DAYS,
  daysUntilExpiry,
  expiryState,
  useStaffCars,
} from '../../hooks/useStaffCars'

const VIEWS = [
  ['', 'All'],
  ['true', 'Expired'],
  ['false', 'Live'],
]

function ExpiryCell({ car, onRenew, isRenewing }) {
  const state = expiryState(car)
  const days = daysUntilExpiry(car)

  if (state === 'never') {
    return <span className="text-ink-soft">Never expires</span>
  }

  const label =
    state === 'expired'
      ? 'Expired'
      : days === 0
        ? 'Expires today'
        : `${days} day${days === 1 ? '' : 's'} left`

  return (
    <span className="flex flex-wrap items-center gap-3">
      {/* Filled marker for anything needing attention; the palette has no
          amber and inventing one for this table would put the product's only
          accent colour on a staff screen. */}
      <span
        aria-hidden="true"
        className={`h-2 w-2 rounded-full ${
          state === 'live' ? 'bg-line' : 'bg-ink'
        }`}
      />
      <span className={state === 'live' ? 'text-ink-soft' : 'text-ink'}>
        {label}
      </span>
      {state !== 'live' && (
        <button
          type="button"
          disabled={isRenewing}
          onClick={() => onRenew(car)}
          className="text-ink underline disabled:opacity-50"
        >
          Renew
        </button>
      )}
    </span>
  )
}

function StaffInventory() {
  const [searchParams, setSearchParams] = useSearchParams()
  const expired = searchParams.get('expired') ?? ''
  const search = searchParams.get('search') ?? ''
  const [term, setTerm] = useState(search)
  const [editing, setEditing] = useState(null)
  const page = Math.max(1, Number(searchParams.get('page') ?? 1))

  const { query, extend, update } = useStaffCars({ search, expired, page })

  function setParam(next) {
    // Page is deliberately dropped: changing a filter or a search puts you on
    // a different result set, and page 4 of it probably does not exist.
    const params = {}
    if (next.expired ?? expired) params.expired = next.expired ?? expired
    if (next.search ?? search) params.search = next.search ?? search
    setSearchParams(params)
  }

  const cars = query.data?.results ?? []
  const needingAttention = cars.filter(
    (car) => expiryState(car) === 'expired' || expiryState(car) === 'soon',
  ).length

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-6">
        <nav className="flex flex-wrap gap-6">
          {VIEWS.map(([value, label]) => (
            <button
              key={label}
              type="button"
              onClick={() => setParam({ expired: value })}
              className={`text-meta transition-colors ${
                expired === value ? 'text-ink underline' : 'text-ink-soft hover:text-ink'
              }`}
            >
              {label}
            </button>
          ))}
        </nav>

        <form
          onSubmit={(event) => {
            event.preventDefault()
            setParam({ search: term.trim() })
          }}
        >
          <input
            type="search"
            value={term}
            onChange={(event) => setTerm(event.target.value)}
            placeholder="Make, model or chassis"
            className="h-10 w-[280px] rounded-full bg-search px-5 text-meta outline-none placeholder:text-ink-mute"
          />
        </form>
      </div>

      {needingAttention > 0 && expired !== 'true' && (
        <p className="mt-8 border border-line bg-surface p-4 text-meta text-ink-soft">
          {needingAttention} listing{needingAttention === 1 ? '' : 's'} on this page{' '}
          {needingAttention === 1 ? 'is' : 'are'} expired or within{' '}
          {EXPIRING_SOON_DAYS} days of it.{' '}
          <button
            type="button"
            onClick={() => setParam({ expired: 'true' })}
            className="text-ink underline"
          >
            Show the expired ones
          </button>
        </p>
      )}

      <div className="mt-8">
        {query.isPending ? (
          <div className="h-64 w-full animate-pulse bg-line" />
        ) : query.isError ? (
          <ErrorState message="We could not load the inventory." onRetry={query.refetch} />
        ) : cars.length === 0 ? (
          <EmptyState
            title="Nothing here"
            message={
              search
                ? `Nothing matches "${search}".`
                : expired === 'true'
                  ? 'No listings have lapsed. '
                  : 'No listings yet.'
            }
          />
        ) : (
          <div className="overflow-x-auto border border-line bg-surface">
            <table className="w-full min-w-[880px] text-meta">
              <thead>
                <tr className="border-b border-line text-badge uppercase text-ink-soft">
                  <th className="px-4 py-3 text-left font-normal">Vehicle</th>
                  <th className="px-4 py-3 text-left font-normal">Price</th>
                  <th className="px-4 py-3 text-left font-normal">Status</th>
                  <th className="px-4 py-3 text-left font-normal">Chassis</th>
                  <th className="px-4 py-3 text-left font-normal">Listing</th>
                  <th className="px-4 py-3 text-right font-normal">Edit</th>
                </tr>
              </thead>
              <tbody>
                {cars.map((car) => (
                  <tr key={car.id} className="border-b border-line last:border-0">
                    <td className="px-4 py-3">
                      <Link to={`/cars/${car.id}`} className="underline">
                        {car.year} {car.make} {car.model}
                      </Link>
                    </td>
                    <td className="px-4 py-3">{formatPrice(car.price)}</td>
                    <td className="px-4 py-3 capitalize text-ink-soft">
                      {car.availability}
                    </td>
                    <td className="px-4 py-3 text-ink-soft">
                      {car.vin || car.reference || '—'}
                    </td>
                    <td className="px-4 py-3">
                      <ExpiryCell
                        car={car}
                        isRenewing={extend.isPending}
                        onRenew={(target) => extend.mutate({ id: target.id })}
                      />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => setEditing(car)}
                        className="text-ink underline"
                      >
                        Edit
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {query.data && (
        <Pagination
          count={query.data.count}
          hasNext={Boolean(query.data.next)}
          hasPrevious={Boolean(query.data.previous)}
        />
      )}

      {editing && (
        <CarEditModal
          car={editing}
          mutation={update}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  )
}

export default StaffInventory
