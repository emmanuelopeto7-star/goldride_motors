import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import CorrectPaymentModal from '../../components/CorrectPaymentModal'
import DispatchPaymentModal from '../../components/DispatchPaymentModal'
import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import Pagination from '../../components/Pagination'
import PaymentHistory from '../../components/PaymentHistory'
import RaisePaymentModal from '../../components/RaisePaymentModal'
import RecordPaymentModal from '../../components/RecordPaymentModal'
import { counted, formatPrice } from '../../lib/format'
import {
  STATUSES,
  useReconciliationRuns,
  useStaffPayments,
} from '../../hooks/useStaffPayments'
import Button from '../../components/Button'

const VIEWS = [['', 'All'], ...STATUSES]

/** "6 minutes ago" rather than a timestamp: the question this answers is
 *  whether the sweep is alive, and a clock time makes the reader do the
 *  subtraction themselves. */
function howLongAgo(value) {
  const minutes = Math.round((Date.now() - new Date(value)) / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${counted(minutes, 'minute')} ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${counted(hours, 'hour')} ago`
  return `${counted(Math.round(hours / 24), 'day')} ago`
}

function StaffPayments() {
  const [searchParams, setSearchParams] = useSearchParams()
  const status = searchParams.get('status') ?? 'pending'
  const page = Math.max(1, Number(searchParams.get('page') ?? 1))
  const [dispatching, setDispatching] = useState(null)
  const [recording, setRecording] = useState(null)
  const [correcting, setCorrecting] = useState(null)
  // One at a time: a history is a wall of text, and twelve of them open at
  // once is a screen nobody can find a payment in.
  const [showingHistory, setShowingHistory] = useState(null)
  const [raising, setRaising] = useState(false)
  // Arriving from an order on the Orders screen, which is where somebody
  // usually notices that money is owed. In the URL rather than in state so
  // the link works from anywhere and survives a refresh.
  const raiseFor = searchParams.get('raise')

  const {
    query,
    createPayment,
    dispatchPayment,
    recordPayment,
    correctPayment,
    reconcileOne,
    reconcileAll,
    canDispatch,
    canRaise,
    canRecord,
    canCorrect,
  } = useStaffPayments({ status, page })

  function openRaise() {
    createPayment.reset()
    setRaising(true)
  }

  function closeRaise() {
    setRaising(false)
    if (raiseFor) {
      const params = new URLSearchParams(searchParams)
      params.delete('raise')
      setSearchParams(params, { replace: true })
    }
  }

  const payments = query.data?.results ?? []
  const runs = useReconciliationRuns()
  // The newest sweep that actually ran. One that stood down because another
  // held the lock says nothing about whether the payments are current.
  const lastRun = (runs.data?.runs ?? []).find(
    (run) => run.finished_at && !run.error.includes('already running'),
  )
  const sinceLastRun = lastRun ? howLongAgo(lastRun.finished_at) : ''

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

        <div className="flex flex-wrap items-center gap-4">
          <Button
            variant="secondary"
            disabled={reconcileAll.isPending}
            onClick={() => reconcileAll.mutate()}
          >
            {reconcileAll.isPending ? 'Checking...' : 'Check all with the provider'}
          </Button>

          {/* Sales too. The amount is capped at what the order still owes,
              so raising one cannot invent a debt. */}
          {canRaise && (
            <Button onClick={openRaise}>
              Raise a payment
            </Button>
          )}
        </div>
      </div>

      {/* A sweep that quietly stopped looks exactly like a quiet week, so
          the screen says when it last ran rather than leaving staff to trust
          that it does. */}
      {lastRun && (
        <p className="mt-8 text-meta text-ink-mute">
          {lastRun.state === 'failed' ? (
            <span className="text-ink">
              The last automatic check failed: {lastRun.error}
            </span>
          ) : (
            <>
              Checked automatically {sinceLastRun}, every{' '}
              {counted(runs.data.interval_minutes, 'minute')}.
            </>
          )}
        </p>
      )}

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
          Checked {counted(sweep.checked, 'pending payment')}.{' '}
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

                {/* The only payment with no provider record behind it, so who
                    said the money arrived is part of the record. */}
                {payment.recorded_at && (
                  <p className="mt-2 text-meta text-ink-soft">
                    Recorded by {payment.recorded_by_name ?? 'a colleague'} on{' '}
                    {new Date(payment.recorded_at).toLocaleDateString('en-KE')}
                    {payment.provider_ref && ` · ${payment.provider_ref}`}
                  </p>
                )}

                <div className="mt-6 flex flex-wrap items-center gap-4 border-t border-line pt-6">
                  {/* Not offered on a bank transfer: there is no provider to
                      ask, and reconciliation can only answer "staff decides". */}
                  {payment.method !== 'manual' && (
                    <Button
                      variant="secondary"
                      disabled={reconcileOne.isPending}
                      onClick={() => reconcileOne.mutate(payment.reference)}
                    >
                      Check with provider
                    </Button>
                  )}

                  {/* A bank transfer has nothing to send, so this is the only
                      thing that can close it. */}
                  {canRecord
                    && payment.method === 'manual'
                    && payment.status === 'pending' && (
                    <Button
                      onClick={() => {
                        recordPayment.reset()
                        setRecording(payment)
                      }}
                    >
                      Record it as received
                    </Button>
                  )}

                  {/* Only while there is something to collect. The API
                      refuses a settled payment anyway. */}
                  {canDispatch
                    && payment.method !== 'manual'
                    && payment.status === 'pending' && (
                    <Button
                      onClick={() => {
                        dispatchPayment.reset()
                        setDispatching(payment)
                      }}
                    >
                      {payment.checkout_sent_at ? 'Send again' : 'Ask for payment'}
                    </Button>
                  )}

                  <Button
                    variant="quiet"
                    onClick={() =>
                      setShowingHistory(
                        showingHistory === payment.reference
                          ? null
                          : payment.reference,
                      )
                    }
                  >
                    {showingHistory === payment.reference
                      ? 'Hide the history'
                      : 'History'}
                  </Button>

                  {/* The one control that overrules a provider, so it is a
                      manager's and it reads as an exception rather than a
                      next step. */}
                  {canCorrect && (
                    <Button
                      variant="quiet"
                      onClick={() => {
                        correctPayment.reset()
                        setCorrecting(payment)
                      }}
                    >
                      Correct it
                    </Button>
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

                {showingHistory === payment.reference && (
                  <div className="mt-6 border-t border-line pt-6">
                    <PaymentHistory reference={payment.reference} />
                  </div>
                )}
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

      {correcting && (
        <CorrectPaymentModal
          payment={correcting}
          mutation={correctPayment}
          onClose={() => setCorrecting(null)}
        />
      )}

      {(raising || raiseFor) && canRaise && (
        <RaisePaymentModal
          orderId={raiseFor}
          mutation={createPayment}
          onClose={closeRaise}
          // Raising and collecting are two steps on purpose, but they are one
          // job - so the second one is offered rather than left to be found.
          onRaised={(payment) => {
            closeRaise()
            dispatchPayment.reset()
            setDispatching(payment)
          }}
        />
      )}

      {recording && (
        <RecordPaymentModal
          payment={recording}
          mutation={recordPayment}
          onClose={() => setRecording(null)}
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
