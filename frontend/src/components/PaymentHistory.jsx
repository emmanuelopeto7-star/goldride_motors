import { usePaymentHistory } from '../hooks/useStaffPayments'

/** Everything that has ever happened to one payment.
 *
 *  The row says what a payment is now. This says how it got there, which is a
 *  different question and usually the one being asked: a payment reading
 *  `failed` could have been failed by Paystack, by the sweep, or by a manager
 *  at four in the afternoon, and those are three different conversations to
 *  have with a customer.
 */

const SOURCE_HINT = {
  webhook: 'Paystack told us, and we re-checked with them before believing it',
  callback: 'Safaricom told us, and we re-queried before believing it',
  reconcile: 'We asked the provider, rather than waiting to be told',
  recorded: 'A person read a bank statement and said so',
  correction: 'Put right by hand, overruling what the provider said',
}

function when(value) {
  return new Date(value).toLocaleString('en-KE', {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

function PaymentHistory({ reference }) {
  const { data, isLoading, isError } = usePaymentHistory(reference)

  if (isLoading) {
    return <div className="h-20 w-full animate-pulse bg-line" />
  }

  if (isError) {
    return (
      <p className="text-meta text-ink-soft">
        The history could not be loaded.
      </p>
    )
  }

  const events = data?.events ?? []

  if (events.length === 0) {
    return (
      <p className="text-meta text-ink-mute">
        Nothing has happened to this payment yet — it was raised and is waiting.
      </p>
    )
  }

  return (
    <ol className="space-y-4">
      {events.map((event) => (
        <li key={event.id} className="flex gap-4">
          <span
            aria-hidden="true"
            className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
              event.source === 'correction' ? 'bg-ink' : 'bg-line-hover'
            }`}
          />
          <div className="min-w-0">
            <p className="text-meta">
              <span className="text-ink-soft">{event.from_status}</span>
              {' → '}
              <span className="text-ink">{event.to_status}</span>
              {' · '}
              {event.source_label}
              {event.actor_name && ` · ${event.actor_name}`}
            </p>
            <p className="mt-1 text-meta text-ink-mute">
              {when(event.created_at)}
              {SOURCE_HINT[event.source] ? ` · ${SOURCE_HINT[event.source]}` : ''}
            </p>
            {event.detail && (
              <p className="mt-1 max-w-[560px] text-meta text-ink-soft">
                {event.detail}
              </p>
            )}
          </div>
        </li>
      ))}
    </ol>
  )
}

export default PaymentHistory
