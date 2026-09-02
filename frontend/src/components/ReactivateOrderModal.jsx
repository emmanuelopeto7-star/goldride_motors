import { useState } from 'react'
import Modal from './Modal'
import { errorMessages } from '../lib/errors'
import Button from './Button'

/** Winning back a cancelled order.
 *
 *  The message is required by the API and rightly so - reopening an order
 *  silently leaves the customer to discover it on a tracking page they had
 *  stopped watching, which is not re-engagement. Say what changed: a
 *  discount, a unit found, a date brought forward.
 */
function ReactivateOrderModal({ order, mutation, onClose }) {
  const [message, setMessage] = useState('')

  function handleSubmit(event) {
    event.preventDefault()
    mutation.mutate({ orderId: order.id, message }, { onSuccess: onClose })
  }

  return (
    <Modal onClose={onClose}>
      <h2 className="text-center font-serif text-section">Win it back</h2>
      <p className="mt-2 text-center text-meta text-ink-soft">
        {order.customer_name} · {order.car_description}
      </p>

      {order.cancel_reason && (
        <p className="mt-6 border border-line p-4 text-meta leading-relaxed text-ink-soft">
          They said: {order.cancel_reason}
        </p>
      )}

      <form onSubmit={handleSubmit} className="mt-6">
        <label htmlFor="offer" className="text-badge uppercase text-ink-soft">
          What has changed?
        </label>
        <textarea
          id="offer"
          rows={4}
          required
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="We can do 200,000 off if you still want it."
          className="mt-2 w-full border border-line bg-surface p-3 text-meta outline-none focus:border-ink"
        />
        <p className="mt-2 text-meta text-ink-mute">
          Emailed to them as written, with a link back to the order.
        </p>

        {mutation.isError && (
          <ul className="mt-4">
            {errorMessages(mutation.error).map((text) => (
              <li key={text} className="text-meta text-ink">{text}</li>
            ))}
          </ul>
        )}

        <Button
          size="large"
          className="mt-8 w-full"
          type="submit"
          disabled={mutation.isPending}
        >
          {mutation.isPending ? 'Sending...' : 'Reopen and send'}
        </Button>
      </form>
    </Modal>
  )
}

export default ReactivateOrderModal
