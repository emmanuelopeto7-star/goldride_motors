import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import { formatPrice } from '../lib/format'
import EmptyState from '../components/EmptyState'
import ErrorState from '../components/ErrorState'

const STATUS_LABEL = {
  pending: 'Awaiting review',
  approved: 'Approved',
  rejected: 'Declined',
}

function MyRequests() {
  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ['my-requests'],
    queryFn: async () => {
      const res = await api.get('/api/purchases/')
      return res.data
    },
  })

  if (isPending) return <div className="h-64 w-full animate-pulse bg-line" />

  if (isError) {
    return <ErrorState message="We could not load your requests." onRetry={refetch} />
  }

  const requests = data.results ?? data

  if (requests.length === 0) {
    return (
      <EmptyState
        title="No requests yet"
        message="When you ask to buy a car it appears here while our team reviews it."
        action={
          <Link to="/" className="mt-8 inline-block text-meta text-ink underline">
            Browse cars
          </Link>
        }
      />
    )
  }

  return (
    <div className="space-y-4">
      {requests.map((request) => (
        <article key={request.id} className="border border-line bg-surface p-6">
          <div className="flex flex-wrap items-baseline justify-between gap-4">
            <h2 className="text-model">{request.car_display}</h2>
            <span className="text-badge uppercase text-ink-soft">
              {STATUS_LABEL[request.status] ?? request.status}
            </span>
          </div>

          <p className="mt-2 text-price font-semibold">{formatPrice(request.price)}</p>

          <dl className="mt-4 flex flex-wrap gap-x-12 gap-y-2 text-meta text-ink-soft">
            <div className="flex gap-2">
              <dt>Preferred method</dt>
              <dd className="uppercase text-ink">{request.preferred_method}</dd>
            </div>
            <div className="flex gap-2">
              <dt>Requested</dt>
              <dd className="text-ink">
                {new Date(request.created_at).toLocaleDateString('en-KE')}
              </dd>
            </div>
          </dl>

          {/* The reason a request was declined is the whole point of showing it. */}
          {request.decision_note && (
            <p className="mt-4 border-t border-line pt-4 text-meta text-ink-soft">
              {request.decision_note}
            </p>
          )}

          {request.status === 'approved' && (
            <Link
              to="/my/orders"
              className="mt-4 inline-block text-meta text-ink underline"
            >
              View the order
            </Link>
          )}
        </article>
      ))}
    </div>
  )
}

export default MyRequests
