import { useState } from 'react'
import Modal from './Modal'
import { errorMessages } from '../lib/errors'
import Button from './Button'

const fieldClass =
  'h-12 w-full border border-line bg-surface px-4 text-model outline-none focus:border-ink'
const labelClass = 'text-badge uppercase text-ink-soft'

/** Correcting an order after the fact.
 *
 *  Deliberately the details and nothing else. The stage is not here because
 *  it follows from the milestones on the server - writing it directly would
 *  leave the headline disagreeing with the timeline underneath it - and
 *  cancelling has its own endpoint so the car's availability moves with it.
 */
function OrderEditModal({ order, mutation, onClose }) {
  const [values, setValues] = useState({
    customer_name: order.customer_name ?? '',
    phone: order.phone ?? '',
    car_description: order.car_description ?? '',
    total_amount: order.total_amount ?? '',
  })

  function set(field) {
    return (event) =>
      setValues((current) => ({ ...current, [field]: event.target.value }))
  }

  function handleSubmit(event) {
    event.preventDefault()
    mutation.mutate({ orderId: order.id, ...values }, { onSuccess: onClose })
  }

  return (
    <Modal onClose={onClose}>
      <h2 className="text-center font-serif text-section">Edit this order</h2>

      <form onSubmit={handleSubmit} className="mt-8 grid gap-6">
        <div>
          <label htmlFor="o-name" className={labelClass}>Customer</label>
          <input id="o-name" required value={values.customer_name} onChange={set('customer_name')} className={`mt-2 ${fieldClass}`} />
        </div>

        <div>
          <label htmlFor="o-phone" className={labelClass}>Phone</label>
          <input id="o-phone" required value={values.phone} onChange={set('phone')} className={`mt-2 ${fieldClass}`} />
        </div>

        <div>
          <label htmlFor="o-car" className={labelClass}>Car</label>
          <input id="o-car" required value={values.car_description} onChange={set('car_description')} className={`mt-2 ${fieldClass}`} />
        </div>

        <div>
          <label htmlFor="o-total" className={labelClass}>Total (KES)</label>
          <input id="o-total" type="number" step="0.01" value={values.total_amount} onChange={set('total_amount')} className={`mt-2 ${fieldClass}`} />
          <p className="mt-2 text-meta text-ink-mute">
            What is still owed is worked out from this and the payments received.
          </p>
        </div>

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
          disabled={mutation.isPending}
        >
          {mutation.isPending ? 'Saving...' : 'Save changes'}
        </Button>
      </form>
    </Modal>
  )
}

export default OrderEditModal
