import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import { formatPrice } from '../lib/format'
import EmptyState from '../components/EmptyState'
import ErrorState from '../components/ErrorState'
import OrderProgress from '../components/OrderProgress'
import PaymentRow from '../components/PaymentRow'

function MyOrders() {
  // After an M-PESA push the outcome arrives at the server, not here, so the
  // page polls for a couple of minutes rather than claiming success itself.
  const [pollUntil, setPollUntil] = useState(0)

  const orders = useQuery({
    queryKey: ['my-orders'],
    queryFn: async () => {
      const res = await api.get('/api/my/orders/')
      return res.data
    },
  })

  const payments = useQuery({
    queryKey: ['my-payments'],
    queryFn: async () => {
      const res = await api.get('/api/payments/mine/')
      return res.data
    },
    refetchInterval: () => (Date.now() < pollUntil ? 5000 : false),
  })

  if (orders.isPending) return <div className="h-64 w-full animate-pulse bg-line" />

  if (orders.isError) {
    return (
      <ErrorState message="We could not load your orders." onRetry={orders.refetch} />
    )
  }

  const orderList = orders.data.results ?? orders.data
  const paymentList = payments.data?.results ?? payments.data ?? []

  if (orderList.length === 0) {
    return (
      <EmptyState
        title="No orders yet"
        message="When a purchase is approved it appears here, with its payment and import progress."
        action={
          <Link to="/" className="mt-8 inline-block text-meta text-ink underline">
            Browse cars
          </Link>
        }
      />
    )
  }

  return (
    <>
      <div className="space-y-8">
        {orderList.map((order) => {
          const mine = paymentList.filter((payment) => payment.order === order.id)

          return (
            <article key={order.id} className="border border-line bg-surface p-6 lg:p-8">
              <div className="flex flex-wrap items-baseline justify-between gap-4">
                <h2 className="font-serif text-section">{order.car_description}</h2>
                <span className="text-badge uppercase text-ink-soft">
                  {order.is_settled ? 'Settled' : 'Balance outstanding'}
                </span>
              </div>

              <div className="mt-6">
                <OrderProgress currentStage={order.current_stage} />
              </div>

              <dl className="mt-8 flex flex-wrap gap-x-16 gap-y-4">
                <div>
                  <dd className="text-price">{formatPrice(order.total_amount)}</dd>
                  <dt className="mt-1 text-meta text-ink-soft">Total</dt>
                </div>
                <div>
                  <dd className="text-price">{formatPrice(order.amount_paid)}</dd>
                  <dt className="mt-1 text-meta text-ink-soft">Paid</dt>
                </div>
                <div>
                  <dd className="text-price">{formatPrice(order.balance)}</dd>
                  <dt className="mt-1 text-meta text-ink-soft">Balance</dt>
                </div>
              </dl>

              <div className="mt-8">
                <p className="text-badge uppercase text-ink-soft">Payments</p>
                {mine.length === 0 ? (
                  <p className="mt-3 text-meta text-ink-soft">
                    Nothing to pay on this order yet.
                  </p>
                ) : (
                  <div className="mt-3">
                    {mine.map((payment) => (
                      <PaymentRow
                        key={payment.reference}
                        payment={payment}
                        onPushSent={() => setPollUntil(Date.now() + 120000)}
                      />
                    ))}
                  </div>
                )}
              </div>

              {order.token && (
                <Link
                  to={`/track/${order.token}`}
                  className="mt-8 inline-block text-meta text-ink underline"
                >
                  Tracking link
                </Link>
              )}

              {order.milestones?.length > 0 && (
                <details className="mt-8">
                  <summary className="cursor-pointer text-meta text-ink underline">
                    Import history
                  </summary>
                  <ul className="mt-4 space-y-3">
                    {order.milestones.map((milestone) => (
                      <li key={`${milestone.stage}-${milestone.created_at}`}>
                        <p className="text-meta uppercase text-ink-soft">
                          {milestone.stage.replace('_', ' ')} ·{' '}
                          {new Date(milestone.created_at).toLocaleDateString('en-KE')}
                        </p>
                        {milestone.note && (
                          <p className="text-model text-ink-soft">{milestone.note}</p>
                        )}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </article>
          )
        })}
      </div>
    </>
  )
}

export default MyOrders
