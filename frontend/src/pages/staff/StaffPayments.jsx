import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import DispatchPaymentModal from '../../components/DispatchPaymentModal'
import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import Pagination from '../../components/Pagination'
import { formatPrice } from '../../lib/format'
import { STATUSES, useStaffPayments } from '../../hooks/useStaffPayments'

const VIEWS = [['', 'All'], ...STATUSES]

function StaffPayments() {
  const [searchParams, setSearchParams] = useSearchParams()
  const status = searchParams.get('status') ?? 'pending'
  const page = Math.max(1, Number(searchParams.get('page') ?? 1))
  const [dispatching, setDispatching] = useState(null)

  const {
    query,
    dispatchPayment,
    reconcileOne,
    reconcileAll,
    canDispatch,
  } = useStaffPayments({ status, page })

  const payments = query.data?.results ?? []
  const sweep = reconcileAll.data
  const single = reconcileOne.data

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-6">
        <nav className="flex flex-wrap gap-6">
          {VIEWS.map(([value, label]) => (
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

        <button
          type="button"
          disabled={reconcileAll.isPending}
          onClick={() => reconcileAll.mutate()}
          className="h-10 border border-ink px-5 text-badge uppercase disabled:opacity-50"
        >
          {reconcileAll.isPending ? 'Checking...' : 'Check all with the provider'}
        </button>
      </div>

      {/* Reported at the top, not on the row. Reconciling a payment usually
          changes its status, which drops it out of the filtered view - so a
          message attached to the row disappears along with the row, and the
          payment appears to vanish for no reason. */}
      {single && (
        <p className="mt-8 border border-line bg-surface p-4 text-meta text-ink-soft">
          Payment {single.reference.slice(0, 8)}: the provider says{' '}
          <span className="text-ink">{single.detail}</span>.{' '}
          {single.changed
            ? `Updated to ${single.status}${
                single.status !== status && status
                  ? ` — it has moved out of this view.`
                  : '.'
              }`
            : 'Nothing changed.'}
        </p>
      )}

      {/* Not a refresh. Webhooks get dropped, and this has caught payments
          that were taken but never recorded against an order. */}
      {sweep && (
        <p className="mt-8 border border-line bg-surface p-4 text-meta text-ink-soft">
          Checked {sweep.checked} pending payment{sweep.checked === 1 ? '' : 's'}.{' '}
          {sweep.updated > 0 ? (
            <span className="text-ink">
              {sweep.updated} had moved without us hearing about it.
            </span>
          ) : (
            'Nothing had changed.'
          )}
        </p>
      )}

      <div className="mt-8">
        {query.isPending ? (
          <div className="h-64 w-full animate-pulse bg-line" />
        ) : query.isError ? (
          <ErrorState message="We could not load the payments." onRetry={query.refetch} />
        ) : payments.length === 0 ? (
          <EmptyState
            title="Nothing here"
            message={
              status === 'pending'
                ? 'Nothing is waiting to be collected.'
                : 'No payments with that status.'
            }
          />
        ) : (
          <ul className="space-y-4">
            {payments.map((payment) => (
              <li key={payment.reference} className="border border-line bg-surface p-6">
                <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
                  <div>
                    <div className="flex flex-wrap items-center gap-3">
                      <p className="text-model">{payment.order_display}</p>
                      <span
                        className={`rounded-full px-3 py-1 text-badge uppercase ${
                          payment.status === 'paid'
                            ? 'bg-ink text-surface'
                            : 'border border-line text-ink-soft'
                        }`}
                      >
                        {payment.status}
                      </span>
                    </div>
                    <p className="mt-1 text-meta text-ink-soft">
                      {payment.method} · {payment.reference.slice(0, 8)}
                    </p>
                  </div>

                  <p className="text-price">{formatPrice(payment.amount)}</p>
                </div>

                {/* The difference between waiting on them and waiting on us,
                    which is the first question anyone asks about a payment
                    that has not moved. */}
                {payment.status === 'pending' && (
                  <p className="mt-4 text-meta text-ink-soft">
                    {payment.checkout_sent_at
                      ? `Customer told on ${new Date(
                          payment.checkout_sent_at,
                        ).toLocaleDateString('en-KE')} — waiting on them.`
                      : 'The customer has not been told how to pay yet.'}
                  </p>
                )}

                {payment.note && (
                  <p className="mt-2 text-meta text-ink-soft">{payment.note}</p>
                )}

                <div className="mt-6 flex flex-wrap items-center gap-4 border-t border-line pt-6">
                  <button
                    type="button"
                    disabled={reconcileOne.isPending}
                    onClick={() => reconcileOne.mutate(payment.reference)}
                    className="h-11 border border-ink px-6 text-badge uppercase disabled:opacity-50"
                  >
                    Check with provider
                  </button>

                  {/* Manager only, and only while there is something to
                      collect. The API refuses a settled payment anyway. */}
                  {canDispatch && payment.status === 'pending' && (
                    <button
                      type="button"
                      onClick={() => {
                        dispatchPayment.reset()
                        setDispatching(payment)
                      }}
                      className="h-11 bg-ink px-6 text-badge uppercase text-surface"
                    >
                      {payment.checkout_sent_at ? 'Send again' : 'Ask for payment'}
                    </button>
                  )}

                  {payment.checkout_url && (
                    <a
                      href={payment.checkout_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-meta text-ink underline"
                    >
                      Their checkout link
                    </a>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {query.data && (
        <Pagination
          count={query.data.count}
          hasNext={Boolean(query.data.next)}
          hasPrevious={Boolean(query.data.previous)}
        />
      )}

      {dispatching && (
        <DispatchPaymentModal
          payment={dispatching}
          mutation={dispatchPayment}
          onClose={() => setDispatching(null)}
        />
      )}
    </div>
  )
}

export default StaffPayments
