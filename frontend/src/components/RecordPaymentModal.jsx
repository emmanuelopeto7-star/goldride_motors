import { useState } from 'react'
import Modal from './Modal'
import { errorMessages } from '../lib/errors'
import { formatPrice } from '../lib/format'
import Button from './Button'

const fieldClass =
  'h-12 w-full border border-line bg-surface px-4 text-model outline-none focus:border-ink'
const labelClass = 'text-badge uppercase text-ink-soft'

/** Say that a bank transfer arrived.
 *
 *  The only payment nobody can be asked about. A card payment is believed
 *  after re-querying Paystack and an M-PESA one after re-querying Safaricom;
 *  a transfer into the account has no callback, so somebody reads a statement
 *  and says so - and the record then names them.
 *
 *  The bank reference is required rather than optional, because it is the
 *  only thing that ties this row back to a line on the statement. Six months
 *  later, "paid" with nothing beside it is not a record of anything.
 */
function RecordPaymentModal({ payment, mutation, onClose }) {
  const [values, setValues] = useState({ provider_ref: '', note: '' })

  function set(field) {
    return (event) =>
      setValues((current) => ({ ...current, [field]: event.target.value }))
  }

  function handleSubmit(event) {
    event.preventDefault()
    mutation.mutate(
      { reference: payment.reference, ...values },
      { onSuccess: onClose },
    )
  }

  return (
    <Modal onClose={onClose}>
      <h2 className="text-center font-serif text-section">Record it as received</h2>
      <p className="mt-2 text-center text-meta text-ink-soft">
        {payment.order_display}
      </p>
      <p className="mt-1 text-center text-price">{formatPrice(payment.amount)}</p>

      <form onSubmit={handleSubmit} className="mt-8 grid gap-6">
        <div>
          <label htmlFor="rec-ref" className={labelClass}>Bank reference</label>
          <input
            id="rec-ref"
            required
            value={values.provider_ref}
            onChange={set('provider_ref')}
            placeholder="As it reads on the statement"
            className={`mt-2 ${fieldClass}`}
          />
        </div>

        <div>
          <label htmlFor="rec-note" className={labelClass}>Note (optional)</label>
          <input
            id="rec-note"
            value={values.note}
            onChange={set('note')}
            placeholder="Equity, cleared 12 Aug"
            className={`mt-2 ${fieldClass}`}
          />
        </div>

        {/* There is no un-pay. Said plainly rather than left to be found out. */}
        <p className="border border-line p-4 text-meta leading-relaxed text-ink-soft">
          This marks the payment paid and reduces the order's balance by{' '}
          {formatPrice(payment.amount)}. It is recorded against your name and
          cannot be undone from here.
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
          disabled={mutation.isPending}
        >
          {mutation.isPending ? 'Recording...' : 'It has arrived'}
        </Button>
      </form>
    </Modal>
  )
}

export default RecordPaymentModal
