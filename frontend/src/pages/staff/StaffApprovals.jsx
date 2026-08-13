import { useSearchParams } from 'react-router-dom'
import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import { usePurchaseRequests } from '../../hooks/usePurchaseRequests'

/** SCAFFOLD - the screen itself is yours to build.
 *
 *  Wired up already: the query, the two mutations, the role check, and the
 *  loading / error / empty states. What renders below the marker is a plain
 *  dump of each request so you can see the shape of the data; replace it.
 *
 *  Fields on a request:
 *    id · car · car_display · price · preferred_method · phone · message
 *    status · decision_note · created_at · reviewed_at · order
 *    customer_username · customer_email · reviewed_by_username
 *
 *  Three things worth designing around:
 *
 *  1. `canDecide` is false for Sales. They can read this queue and act on
 *     nothing, so the screen has to explain itself rather than just render
 *     dead buttons.
 *  2. Approving is irreversible and does four things at once - creates the
 *     order, reserves the car, raises the payment, dispatches collection. It
 *     wants a confirm step, not a bare button.
 *  3. Approval succeeding and collection succeeding are separate outcomes.
 *     Pass the mutation result through describeApproval() from the hook and
 *     render what it returns; on most of this inventory the payment rails
 *     refuse the amount and it falls back to manual.
 */
function StaffApprovals() {
  // §"state that should survive a refresh goes in the URL" - the filter is
  // part of what you would send someone in a link.
  const [searchParams] = useSearchParams()
  const status = searchParams.get('status') ?? 'pending'

  const { query, canDecide } = usePurchaseRequests(status)

  if (query.isPending) {
    return <div className="h-64 w-full animate-pulse bg-line" />
  }

  if (query.isError) {
    return (
      <ErrorState
        message="We could not load the approvals queue."
        onRetry={query.refetch}
      />
    )
  }

  const requests = query.data

  if (requests.length === 0) {
    return (
      <EmptyState
        title="Nothing waiting"
        message="Purchase requests appear here as customers send them."
      />
    )
  }

  return (
    <div>
      {!canDecide && (
        <p className="mb-8 border border-line bg-surface p-4 text-meta text-ink-soft">
          You can review this queue, but only a Manager can approve or reject.
        </p>
      )}

      {/* ---- everything below here is placeholder ---- */}
      <ul className="space-y-4">
        {requests.map((request) => (
          <li key={request.id} className="border border-line bg-surface p-6">
            <pre className="overflow-x-auto text-meta text-ink-soft">
              {JSON.stringify(request, null, 2)}
            </pre>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default StaffApprovals
