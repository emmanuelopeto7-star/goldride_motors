import { Link, useSearchParams } from 'react-router-dom'
import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import { formatPrice } from '../../lib/format'
import { useImportRequests } from '../../hooks/useSourcing'

const FILTERS = [
  ['pending', 'To source'],
  ['sourcing', 'In progress'],
  ['awaiting_selection', 'With customer'],
  ['agreed', 'Agreed'],
  ['', 'All'],
]

const EMPTY = {
  pending: 'Nothing waiting to be sourced.',
  sourcing: 'Nothing part-sourced right now.',
  awaiting_selection: 'No customer is currently choosing.',
  agreed: 'Nothing agreed yet.',
  '': 'No import requests have come in yet.',
}

function StaffSourcing() {
  const [searchParams, setSearchParams] = useSearchParams()
  const status = searchParams.get('status') ?? 'pending'
  const { data, isPending, isError, refetch } = useImportRequests(status)

  return (
    <div>
      <nav className="flex flex-wrap gap-6">
        {FILTERS.map(([value, label]) => (
          <button
            key={label}
            type="button"
            onClick={() => setSearchParams(value ? { status: value } : {})}
            className={`text-meta transition-colors ${
              status === value ? 'text-ink underline' : 'text-ink-soft hover:text-ink'
            }`}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="mt-8">
        {isPending ? (
          <div className="h-64 w-full animate-pulse bg-line" />
        ) : isError ? (
          <ErrorState message="We could not load the sourcing queue." onRetry={refetch} />
        ) : data.length === 0 ? (
          <EmptyState title="Nothing here" message={EMPTY[status]} />
        ) : (
          <ul className="space-y-4">
            {data.map((request) => {
              const offered = (request.units ?? []).filter(
                (unit) => unit.status === 'offered',
              ).length
              return (
                <li key={request.id} className="border border-line bg-surface p-6">
                  <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
                    <div>
                      <Link
                        to={`/staff/sourcing/${request.id}`}
                        className="text-model underline"
                      >
                        {request.year} {request.make} {request.model}
                      </Link>
                      <p className="mt-1 text-meta text-ink-soft">
                        {request.contact_name} · {request.phone}
                      </p>
                    </div>

                    <dl className="flex flex-wrap gap-x-12 gap-y-3 text-meta">
                      <div>
                        <dt className="text-ink-soft">Budget</dt>
                        <dd className="mt-1">
                          {request.budget_kes
                            ? formatPrice(request.budget_kes)
                            : 'Not stated'}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-ink-soft">Units</dt>
                        <dd className="mt-1">
                          {(request.units ?? []).length}
                          {offered > 0 && ` · ${offered} on offer`}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-ink-soft">Asked</dt>
                        <dd className="mt-1">
                          {new Date(request.created_at).toLocaleDateString('en-KE')}
                        </dd>
                      </div>
                    </dl>
                  </div>

                  {request.notes && (
                    <p className="mt-4 max-w-[68ch] border-t border-line pt-4 text-meta leading-relaxed text-ink-soft">
                      {request.notes}
                    </p>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}

export default StaffSourcing
