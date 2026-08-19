import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import AdvanceStageModal from '../../components/AdvanceStageModal'
import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import Pagination from '../../components/Pagination'
import ReactivateOrderModal from '../../components/ReactivateOrderModal'
import { formatPrice } from '../../lib/format'
import { STAGES, nextStage, useStaffOrders } from '../../hooks/useStaffOrders'

const VIEWS = [
  ['', '', 'Live'],
  ['ordered', '', 'Ordered'],
  ['shipped', '', 'Shipped'],
  ['at_port', '', 'At port'],
  ['clearing', '', 'Clearing'],
  ['delivered', '', 'Delivered'],
  ['', 'true', 'Cancelled'],
]

function StageRail({ current, cancelled }) {
  const reached = STAGES.findIndex(([key]) => key === current)

  return (
    <ol className="flex flex-wrap gap-x-2 gap-y-2">
      {STAGES.map(([key, label], index) => {
        const done = !cancelled && index <= reached
        return (
          <li key={key} className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className={`h-2 w-2 rounded-full ${done ? 'bg-ink' : 'bg-line'}`}
            />
            <span className={`text-badge uppercase ${done ? 'text-ink' : 'text-ink-mute'}`}>
              {label}
            </span>
            {index < STAGES.length - 1 && (
              <span aria-hidden="true" className="ml-1 h-px w-4 bg-line" />
            )}
          </li>
        )
      })}
    </ol>
  )
}

function StaffOrders() {
  const [searchParams, setSearchParams] = useSearchParams()
  const stage = searchParams.get('stage') ?? ''
  const cancelled = searchParams.get('cancelled') ?? ''
  const page = Math.max(1, Number(searchParams.get('page') ?? 1))

  const [advancing, setAdvancing] = useState(null)
  const [reviving, setReviving] = useState(null)

  const { query, advance, reactivate } = useStaffOrders({ stage, cancelled, page })
  const orders = query.data?.results ?? []

  function selectView(nextStageValue, nextCancelled) {
    const params = {}
    if (nextStageValue) params.stage = nextStageValue
    if (nextCancelled) params.cancelled = nextCancelled
    // Live means "not cancelled", which the API needs told explicitly.
    if (!nextCancelled) params.cancelled = 'false'
    setSearchParams(params)
  }

  const activeView = cancelled === 'true' ? 'cancelled' : stage

  return (
    <div>
      <nav className="flex flex-wrap gap-6">
        {VIEWS.map(([stageValue, cancelledValue, label]) => {
          const key = cancelledValue === 'true' ? 'cancelled' : stageValue
          return (
            <button
              key={label}
              type="button"
              onClick={() => selectView(stageValue, cancelledValue)}
              className={`text-meta transition-colors ${
                activeView === key ? 'text-ink underline' : 'text-ink-soft hover:text-ink'
              }`}
            >
              {label}
            </button>
          )
        })}
      </nav>

      <div className="mt-8">
        {query.isPending ? (
          <div className="h-64 w-full animate-pulse bg-line" />
        ) : query.isError ? (
          <ErrorState message="We could not load the orders." onRetry={query.refetch} />
        ) : orders.length === 0 ? (
          <EmptyState
            title="Nothing here"
            message={
              cancelled === 'true'
                ? 'Nobody has cancelled an order.'
                : 'No orders at this stage.'
            }
          />
        ) : (
          <ul className="space-y-4">
            {orders.map((order) => {
              const upcoming = nextStage(order.current_stage)
              return (
                <li key={order.id} className="border border-line bg-surface p-6">
                  <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
                    <div>
                      <div className="flex flex-wrap items-center gap-3">
                        <p className="text-model">{order.car_description}</p>
                        {order.is_cancelled && (
                          <span className="rounded-full bg-ink px-3 py-1 text-badge uppercase text-surface">
                            Cancelled
                          </span>
                        )}
                        {order.is_settled && !order.is_cancelled && (
                          <span className="rounded-full border border-line px-3 py-1 text-badge uppercase text-ink-soft">
                            Settled
                          </span>
                        )}
                      </div>
                      <p className="mt-1 text-meta text-ink-soft">
                        {order.customer_name} · {order.phone}
                      </p>
                    </div>

                    <dl className="flex flex-wrap gap-x-10 gap-y-3 text-meta">
                      <div>
                        <dt className="text-ink-soft">Total</dt>
                        <dd className="mt-1">{formatPrice(order.total_amount)}</dd>
                      </div>
                      <div>
                        <dt className="text-ink-soft">Paid</dt>
                        <dd className="mt-1">{formatPrice(order.amount_paid)}</dd>
                      </div>
                      <div>
                        <dt className="text-ink-soft">Balance</dt>
                        <dd className="mt-1">{formatPrice(order.balance)}</dd>
                      </div>
                    </dl>
                  </div>

                  <div className="mt-6 border-t border-line pt-6">
                    <StageRail
                      current={order.current_stage}
                      cancelled={order.is_cancelled}
                    />
                  </div>

                  {order.cancel_reason && (
                    <p className="mt-4 text-meta text-ink-soft">
                      They said: {order.cancel_reason}
                    </p>
                  )}

                  {order.milestones?.length > 0 && (
                    <details className="mt-4">
                      <summary className="cursor-pointer text-meta text-ink underline">
                        History ({order.milestones.length})
                      </summary>
                      <ul className="mt-3 space-y-2">
                        {order.milestones.map((milestone) => (
                          <li key={`${milestone.stage}-${milestone.created_at}`}>
                            <p className="text-badge uppercase text-ink-soft">
                              {milestone.stage.replace('_', ' ')} ·{' '}
                              {new Date(milestone.created_at).toLocaleDateString('en-KE')}
                            </p>
                            {milestone.note && (
                              <p className="text-meta text-ink-soft">{milestone.note}</p>
                            )}
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}

                  <div className="mt-6 flex flex-wrap items-center gap-4 border-t border-line pt-6">
                    {order.is_cancelled ? (
                      <button
                        type="button"
                        onClick={() => setReviving(order)}
                        className="h-11 border border-ink px-6 text-badge uppercase"
                      >
                        Win it back
                      </button>
                    ) : (
                      <>
                        <button
                          type="button"
                          onClick={() => setAdvancing(order)}
                          className="h-11 bg-ink px-6 text-badge uppercase text-surface"
                        >
                          {upcoming ? `Mark ${upcoming[1].toLowerCase()}` : 'Add an update'}
                        </button>
                        <a
                          href={`/track/${order.token}`}
                          target="_blank"
                          rel="noreferrer"
                          className="text-meta text-ink underline"
                        >
                          What the customer sees
                        </a>
                      </>
                    )}
                  </div>
                </li>
              )
            })}
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

      {advancing && (
        <AdvanceStageModal
          order={advancing}
          mutation={advance}
          onClose={() => setAdvancing(null)}
        />
      )}

      {reviving && (
        <ReactivateOrderModal
          order={reviving}
          mutation={reactivate}
          onClose={() => setReviving(null)}
        />
      )}
    </div>
  )
}

export default StaffOrders
