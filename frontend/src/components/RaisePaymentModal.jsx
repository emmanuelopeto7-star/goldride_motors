import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import Modal from './Modal'
import api from '../api/client'
import { errorMessages } from '../lib/errors'
import { formatPrice } from '../lib/format'
import { METHODS, MPESA_LIMIT } from '../hooks/useStaffPayments'
import { useStaffOrders } from '../hooks/useStaffOrders'
import Button from './Button'

const fieldClass =
  'h-12 w-full border border-line bg-surface px-4 text-model outline-none focus:border-ink'
const labelClass = 'text-badge uppercase text-ink-soft'

/** Which order the money is for.
 *
 *  A search rather than a dropdown: a dealership's order list is longer than a
 *  select is usable, and the person raising the payment knows the customer's
 *  name or the car, not its id. Cancelled orders are left out - the server
 *  refuses them, so offering one would be offering a dead end.
 */
function OrderPicker({ onPick }) {
  const [term, setTerm] = useState('')
  const [search, setSearch] = useState('')
  const { query } = useStaffOrders({ cancelled: 'false', search })
  const orders = query.data?.results ?? []

  return (
    <div className="mt-8">
      <form
        onSubmit={(event) => {
          event.preventDefault()
          setSearch(term.trim())
        }}
      >
        <label htmlFor="r-search" className={labelClass}>
          Which order
        </label>
        <div className="mt-2 flex gap-3">
          <input
            id="r-search"
            value={term}
            onChange={(event) => setTerm(event.target.value)}
            placeholder="Customer, phone or car"
            className={fieldClass}
          />
          <Button
            variant="secondary"
            size="large"
            type="submit"
          >
            Find
          </Button>
        </div>
      </form>

      {query.isPending ? (
        <div className="mt-6 h-40 w-full animate-pulse bg-line" />
      ) : orders.length === 0 ? (
        <p className="mt-6 text-meta text-ink-soft">
          {search
            ? 'No live order matches that.'
            : 'There are no live orders to bill.'}
        </p>
      ) : (
        <ul className="mt-6 max-h-72 overflow-y-auto border border-line">
          {orders.map((order) => (
            <li key={order.id} className="border-b border-line last:border-b-0">
              <button
                type="button"
                onClick={() => onPick(order)}
                className="w-full px-4 py-3 text-left hover:bg-surface"
              >
                <span className="block text-model">{order.car_description}</span>
                <span className="mt-1 block text-meta text-ink-soft">
                  {order.customer_name} · {formatPrice(order.balance)} outstanding
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* Only ever the first page. Anything beyond it is reached by searching,
          which is faster than paging a picker anyway. */}
      {query.data?.next && (
        <p className="mt-3 text-meta text-ink-mute">
          Showing the most recent {orders.length}. Search to narrow it down.
        </p>
      )}
    </div>
  )
}

/** Raise an invoice against an order.
 *
 *  Raising is not silent: the server posts the figure into the chat about
 *  that car, with a link to pay. What it does not do is email the customer or
 *  push an M-PESA prompt - that is the dispatch step, offered on the way out.
 *  The form says so above the button, because somebody typing an amount
 *  should know the customer sees it the moment it is saved.
 */
function RaisePaymentModal({ orderId, mutation, onClose, onRaised }) {
  const [order, setOrder] = useState(null)
  const [values, setValues] = useState({ amount: '', method: 'card', note: '' })
  // What *this* open raised, rather than mutation.data. The mutation is owned
  // by the page and outlives the modal, and one of the ways in is a URL -
  // /staff/payments?raise=12 from the orders screen - so reading its data
  // would greet whoever follows that link with the last raise's receipt.
  const [raised, setRaised] = useState(null)

  // Arriving from an order on the Orders screen: the order is named in the
  // URL, so the picker is skipped entirely.
  const preselected = useQuery({
    queryKey: ['staff-order', orderId],
    queryFn: async () => (await api.get(`/api/staff/orders/${orderId}/`)).data,
    enabled: Boolean(orderId) && !order,
  })

  // Keyed on the fetched order alone. `pick` is rebuilt every render, and
  // depending on it would re-seed the amount over whatever was typed.
  useEffect(() => {
    if (preselected.data) pick(preselected.data)
  }, [preselected.data])

  function pick(picked) {
    setOrder(picked)
    // What is still owed is the amount being asked for nine times out of ten.
    // Editable, because the tenth is a deposit.
    setValues((current) => ({
      ...current,
      amount: Number(picked.balance) > 0 ? String(picked.balance) : '',
    }))
  }

  function set(field) {
    return (event) =>
      setValues((current) => ({ ...current, [field]: event.target.value }))
  }

  function handleSubmit(event) {
    event.preventDefault()
    mutation.mutate({ order: order.id, ...values }, { onSuccess: setRaised })
  }

  if (raised) {
    // Raising posts into the chat about the car and stamps this. Blank means
    // there was no thread to post in - an order raised for a walk-in never
    // had a purchase request behind it - so nobody has been told anything.
    const told = Boolean(raised.checkout_sent_at)
    const manual = raised.method === 'manual'

    return (
      <Modal onClose={onClose}>
        <h2 className="text-center font-serif text-section">Raised</h2>
        <p className="mt-6 text-center text-price">{formatPrice(raised.amount)}</p>
        <p className="mt-2 text-center text-meta text-ink-soft">
          {raised.order_display}
        </p>

        <p className="mt-6 text-model leading-relaxed text-ink-soft">
          {told
            ? manual
              ? 'The customer has been told in the chat that this one is a bank transfer. Send them the account details yourself, and check it against the statement when it lands.'
              : raised.method === 'mpesa'
                ? 'The customer has been told in the chat, with a link to start the payment themselves. Nothing has reached their phone yet.'
                : 'The customer has been told in the chat, with a link to pay.'
            : manual
              ? 'This order has no chat thread, so nobody has been told. Pass the account details on yourself, and check it against the statement when it lands.'
              : 'This order has no chat thread, so nobody has been told yet.'}
        </p>

        {!manual && (
          <Button
            variant={told ? 'secondary' : 'primary'}
            size="large"
            className="mt-8 w-full"
            onClick={() => onRaised(raised)}
          >
            {raised.method === 'mpesa'
              ? 'Send the M-PESA prompt'
              : told
                ? 'Email it as well'
                : 'Ask for it now'}
          </Button>
        )}

        <Button
          variant={manual || told ? 'primary' : 'secondary'}
          size="large"
          className={manual ? 'mt-8 w-full' : 'mt-3 w-full'}
          onClick={onClose}
        >
          {manual || told ? 'Done' : 'Later'}
        </Button>
      </Modal>
    )
  }

  if (!order) {
    return (
      <Modal onClose={onClose}>
        <h2 className="text-center font-serif text-section">Raise a payment</h2>
        {preselected.isPending && orderId ? (
          <div className="mt-8 h-40 w-full animate-pulse bg-line" />
        ) : (
          <OrderPicker onPick={pick} />
        )}
      </Modal>
    )
  }

  const amount = Number(values.amount)
  const overMpesa = values.method === 'mpesa' && amount > MPESA_LIMIT
  const overBalance =
    Number(order.total_amount) > 0 && amount > Number(order.balance)

  return (
    <Modal onClose={onClose}>
      <h2 className="text-center font-serif text-section">Raise a payment</h2>
      <p className="mt-2 text-center text-meta text-ink-soft">
        {order.car_description} · {order.customer_name}
      </p>

      {/* The three figures the amount has to be judged against. Without them
          the person typing is working from memory. */}
      <dl className="mt-6 flex justify-between border border-line p-4 text-meta">
        <div>
          <dt className="text-ink-soft">Total</dt>
          <dd className="mt-1">{formatPrice(order.total_amount)}</dd>
        </div>
        <div>
          <dt className="text-ink-soft">Paid</dt>
          <dd className="mt-1">{formatPrice(order.amount_paid)}</dd>
        </div>
        <div>
          <dt className="text-ink-soft">Outstanding</dt>
          <dd className="mt-1">{formatPrice(order.balance)}</dd>
        </div>
      </dl>

      <form onSubmit={handleSubmit} className="mt-8 grid gap-6">
        <div>
          <label htmlFor="r-amount" className={labelClass}>Amount (KES)</label>
          <input
            id="r-amount"
            type="number"
            step="0.01"
            min="0"
            required
            value={values.amount}
            onChange={set('amount')}
            className={`mt-2 ${fieldClass}`}
          />
          {overBalance && (
            <p className="mt-2 text-meta text-ink">
              That is more than is outstanding. Raise the order total first if
              the price has moved.
            </p>
          )}
        </div>

        <div>
          <label htmlFor="r-method" className={labelClass}>How they pay</label>
          <select
            id="r-method"
            value={values.method}
            onChange={set('method')}
            className={`mt-2 ${fieldClass}`}
          >
            {METHODS.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
          {overMpesa && (
            <p className="mt-2 text-meta text-ink">
              M-PESA stops at {MPESA_LIMIT.toLocaleString('en-KE')} a
              transaction. This one has to be a bank transfer.
            </p>
          )}
        </div>

        <div>
          <label htmlFor="r-note" className={labelClass}>Note (optional)</label>
          <input
            id="r-note"
            value={values.note}
            onChange={set('note')}
            placeholder="Deposit agreed on the phone"
            className={`mt-2 ${fieldClass}`}
          />
          <p className="mt-2 text-meta text-ink-mute">
            Shown on the payment here. The customer does not see it.
          </p>
        </div>

        {/* Said before the button, not after it. Raising is no longer silent,
            and a manager should know the customer hears about this figure the
            moment it is saved. */}
        <p className="border border-line p-4 text-meta leading-relaxed text-ink-soft">
          The customer is told in the chat about this car, with a link to pay.
          Nothing is emailed and no M-PESA prompt is sent until the next step.
        </p>

        {mutation.isError && (
          <ul>
            {errorMessages(mutation.error).map((message) => (
              <li key={message} className="text-meta text-ink">{message}</li>
            ))}
          </ul>
        )}

        <Button
          size="large"
          className="w-full"
          type="submit"
          disabled={mutation.isPending || overBalance || overMpesa}
        >
          {mutation.isPending ? 'Raising...' : 'Raise it'}
        </Button>

        {!orderId && (
          <button
            type="button"
            onClick={() => setOrder(null)}
            className="text-meta text-ink underline"
          >
            Pick a different order
          </button>
        )}
      </form>
    </Modal>
  )
}

export default RaisePaymentModal
