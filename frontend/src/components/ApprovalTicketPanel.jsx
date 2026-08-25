import { useState } from 'react'
import ApprovalDecisionModal from './ApprovalDecisionModal'
import ErrorState from './ErrorState'
import { formatPrice } from '../lib/format'
import {
  usePurchaseRequest,
  usePurchaseRequests,
} from '../hooks/usePurchaseRequests'

/** The approval branch of a ticket.
 *
 *  This is what the Approvals queue used to render per row, for one request
 *  rather than a list. The decisions themselves have not moved: approve and
 *  reject are still Manager-only and still create the order, reserve the car
 *  and dispatch collection in a single request.
 */
function ApprovalTicketPanel({ requestId }) {
  const { data: request, isPending, isError, refetch } = usePurchaseRequest(requestId)
  // The list hook is here only for its two mutations and the role flag; the
  // request itself comes from the detail endpoint above.
  const { approve, reject, canDecide } = usePurchaseRequests()
  const [deciding, setDeciding] = useState(null)
  const mutation = deciding?.action === 'approve' ? approve : reject

  function open(action) {
    // Clearing first, or the modal opens showing the previous decision's
    // outcome instead of its own confirm step.
    approve.reset()
    reject.reset()
    setDeciding({ action })
  }

  if (isPending) return <div className="h-48 w-full animate-pulse bg-line" />

  if (isError) {
    return (
      <ErrorState message="We could not load this request." onRetry={refetch} />
    )
  }

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
        <div className="min-w-0">
          <p className="text-model">{request.car_title}</p>
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
            <dd className="mt-1 capitalize">{request.preferred_method}</dd>
          </div>
          <div>
            <dt className="text-ink-soft">Status</dt>
            <dd className="mt-1 capitalize">{request.status}</dd>
          </div>
        </dl>
      </div>

      {request.message && (
        <p className="mt-6 max-w-[68ch] whitespace-pre-line border-t border-line pt-6 text-meta leading-relaxed text-ink-soft">
          {request.message}
        </p>
      )}

      {request.decision_note && (
        <p className="mt-6 border-t border-line pt-6 text-meta text-ink-soft">
          {request.reviewed_by_username ?? 'Staff'}: {request.decision_note}
        </p>
      )}

      {!canDecide && request.status === 'pending' && (
        <p className="mt-6 border border-line bg-surface p-4 text-meta text-ink-soft">
          You can work this ticket, but only a Manager can approve or reject.
        </p>
      )}

      {/* Only a pending request can be decided - the API refuses a second
          decision, so offering the buttons would be a lie. */}
      {canDecide && request.status === 'pending' && (
        <div className="mt-6 flex flex-wrap gap-3 border-t border-line pt-6">
          <button
            type="button"
            onClick={() => open('approve')}
            className="h-11 bg-ink px-6 text-badge uppercase text-surface"
          >
            Approve
          </button>
          <button
            type="button"
            onClick={() => open('reject')}
            className="h-11 border border-ink px-6 text-badge uppercase"
          >
            Reject
          </button>
        </div>
      )}

      {deciding && (
        <ApprovalDecisionModal
          action={deciding.action}
          request={request}
          mutation={mutation}
          onClose={() => setDeciding(null)}
        />
      )}
    </div>
  )
}

export default ApprovalTicketPanel
