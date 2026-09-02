import { useState } from 'react'
import Modal from './Modal'
import { errorMessages } from '../lib/errors'
import { formatPrice } from '../lib/format'
import Button from './Button'

const fieldClass =
  'h-12 w-full border border-line bg-surface px-4 text-model outline-none focus:border-ink'
const labelClass = 'text-badge uppercase text-ink-soft'

/** Ask the customer for the money again.
 *
 *  For a card payment this mints a fresh Paystack link and emails it; for
 *  M-PESA it pushes a new STK prompt to the phone. Either way the customer is
 *  emailed their instructions, so this doubles as the resend for someone who
 *  lost the first message.
 *
 *  Both fields default to what is on the order and are editable, because the
 *  commonest reason a dispatch failed is that the address or number on file
 *  was wrong.
 */
function DispatchPaymentModal({ payment, mutation, onClose }) {
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const result = mutation.data

  function handleSubmit(event) {
    event.preventDefault()
    mutation.mutate({ reference: payment.reference, email, phone })
  }

  if (result) {
    return (
      <Modal onClose={onClose}>
        <h2 className="text-center font-serif text-section">Sent</h2>

        <p className="mt-6 text-model leading-relaxed text-ink-soft">
          {result.pay_url
            ? 'A payment link has been created.'
            : result.detail}
          {result.emailed === false &&
            ' We could not email it — there is no address on the order, so pass it on yourself.'}
        </p>

        {/* The durable link, not the checkout session behind it. This is the
            one that gets pasted into a message and read tomorrow; a Paystack
            session would be stale long before then. */}
        {result.pay_url && (
          <>
            <a
              href={result.pay_url}
              target="_blank"
              rel="noreferrer"
              className="mt-6 block break-all text-meta text-ink underline"
            >
              {result.pay_url}
            </a>
            <p className="mt-2 text-meta text-ink-mute">
              Safe to send on - it stays valid until the invoice is paid.
            </p>
          </>
        )}

        <Button
          size="large"
          className="mt-8 w-full"
          onClick={onClose}
        >
          Done
        </Button>
      </Modal>
    )
  }

  return (
    <Modal onClose={onClose}>
      <h2 className="text-center font-serif text-section">Ask for payment</h2>
      <p className="mt-2 text-center text-meta text-ink-soft">
        {payment.order_display}
      </p>
      <p className="mt-1 text-center text-price">{formatPrice(payment.amount)}</p>

      <form onSubmit={handleSubmit} className="mt-8">
        <div>
          <label htmlFor="d-email" className={labelClass}>Email</label>
          <input
            id="d-email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="Leave blank to use the one on the order"
            className={`mt-2 ${fieldClass}`}
          />
        </div>

        <div className="mt-6">
          <label htmlFor="d-phone" className={labelClass}>Phone</label>
          <input
            id="d-phone"
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            placeholder="Leave blank to use the one on the order"
            className={`mt-2 ${fieldClass}`}
          />
        </div>

        <p className="mt-6 border border-line p-4 text-meta leading-relaxed text-ink-soft">
          {payment.method === 'card'
            ? 'Creates a new checkout link and emails it to the customer.'
            : payment.method === 'mpesa'
              ? 'Sends an M-PESA prompt to the phone. Capped at 250,000 — anything above that has to be a bank transfer.'
              : 'This payment is set to manual, so there is nothing to send. Change the method first.'}
        </p>

        {mutation.isError && (
          <ul className="mt-4">
            {errorMessages(mutation.error).map((message) => (
              <li key={message} className="text-meta text-ink">{message}</li>
            ))}
          </ul>
        )}

        <Button
          size="large"
          className="mt-6 w-full"
          type="submit"
          disabled={mutation.isPending || payment.method === 'manual'}
        >
          {mutation.isPending ? 'Sending...' : 'Send it'}
        </Button>
      </form>
    </Modal>
  )
}

export default DispatchPaymentModal
