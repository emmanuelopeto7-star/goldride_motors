import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import ApprovalDecisionModal from '../../components/ApprovalDecisionModal'
import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import { formatPrice } from '../../lib/format'
import { usePurchaseRequests } from '../../hooks/usePurchaseRequests'

const FILTERS = [
  ['pending', 'Pending'],
  ['approved', 'Approved'],
  ['rejected', 'Rejected'],
  ['', 'All'],
]

const EMPTY = {
  pending: 'Purchase requests appear here as customers send them.',
  approved: 'Nothing has been approved yet.',
  rejected: 'Nothing has been rejected yet.',
  '': 'No purchase requests have been made yet.',
}

function StatusBadge({ status }) {
  // Monochrome by §2: an approved row is filled, everything else is outlined.
  // Colour-coding these would put the only accent in the whole product here.
  const filled = status === 'approved'
  return (
    <span
      className={`shrink-0 rounded-full px-3 py-1 text-badge uppercase ${
        filled ? 'bg-ink text-surface' : 'border border-line text-ink-soft'
      }`}
    >
      {status}
    </span>
  )
}

function StaffApprovals() {
  // §"state that should survive a refresh goes in the URL" - the filter is
  // part of what you would send someone in a link.
  const [searchParams, setSearchParams] = useSearchParams()
  const status = searchParams.get('status') ?? 'pending'

  // Which row is being decided, and which way. Local: it is transient, and
  // nobody wants to land on a URL that reopens a confirm dialog.
  const [deciding, setDeciding] = useState(null)

  const { query, approve, reject, canDecide } = usePurchaseRequests(status)
  const mutation = deciding?.action === 'approve' ? approve : reject

  function open(action, request) {
    // Clearing first, or the modal opens showing the previous decision's
    // outcome instead of its own confirm step.
    approve.reset()
    reject.reset()
    setDeciding({ action, request })
  }

  return (
    <div>
      <nav className="flex flex-wrap gap-6">
        {FILTERS.map(([value, label]) => (
          <button
            key={label}
            type="button"
            onClick={() => setSearchParams(value ? { status: value } : {})}
            className={`text-meta transition-colors ${
              status === value
                ? 'text-ink underline'
                : 'text-ink-soft hover:text-ink'
            }`}
          >
            {label}
          </button>
        ))}
      </nav>

      {!canDecide && (
        <p className="mt-8 border border-line bg-surface p-4 text-meta text-ink-soft">
          You can review this queue, but only a Manager can approve or reject.
        </p>
      )}

      <div className="mt-8">
        {query.isPending ? (
          <div className="h-64 w-full animate-pulse bg-line" />
        ) : query.isError ? (
          <ErrorState
            message="We could not load the approvals queue."
            onRetry={query.refetch}
          />
        ) : query.data.length === 0 ? (
          <EmptyState title="Nothing waiting" message={EMPTY[status]} />
        ) : (
          <ul className="space-y-4">
            {query.data.map((request) => (
              <li
                key={request.id}
                className="border border-line bg-surface p-6"
              >
                <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-3">
                      <p className="text-model">{request.car_title}</p>
                      <StatusBadge status={request.status} />
                    </div>
                    <p className="mt-1 text-price">{formatPrice(request.price)}</p>
                  </div>

                  <dl className="flex flex-wrap gap-x-12 gap-y-3 text-meta">
                    <div>
                      <dt className="text-ink-soft">Customer</dt>
                      <dd className="mt-1">{request.customer_username}</dd>
                    </div>
                    <div>
                      <dt className="text-ink-soft">Phone</dt>
                      <dd className="mt-1">{request.phone}</dd>
                    </div>
                    <div>
                      <dt className="text-ink-soft">Prefers</dt>
                      <dd className="mt-1 capitalize">
                        {request.preferred_method}
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

                {request.message && (
                  <p className="mt-4 max-w-[68ch] whitespace-pre-line border-t border-line pt-4 text-meta leading-relaxed text-ink-soft">
                    {request.message}
                  </p>
                )}

                {request.decision_note && (
                  <p className="mt-4 border-t border-line pt-4 text-meta text-ink-soft">
                    {request.reviewed_by_username ?? 'Staff'}:{' '}
                    {request.decision_note}
                  </p>
                )}

                {/* Only pending requests can be decided - the API refuses a
                    second decision, so offering the buttons would be a lie. */}
                {canDecide && request.status === 'pending' && (
                  <div className="mt-6 flex flex-wrap gap-3 border-t border-line pt-6">
                    <button
                      type="button"
                      onClick={() => open('approve', request)}
                      className="h-11 bg-ink px-6 text-badge uppercase text-surface"
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      onClick={() => open('reject', request)}
                      className="h-11 border border-ink px-6 text-badge uppercase"
                    >
                      Reject
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      {deciding && (
        <ApprovalDecisionModal
          action={deciding.action}
          request={deciding.request}
          mutation={mutation}
          onClose={() => setDeciding(null)}
        />
      )}
    </div>
  )
}

export default StaffApprovals
