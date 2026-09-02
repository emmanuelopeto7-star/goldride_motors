import { useState } from 'react'
import Modal from './Modal'
import { formatPrice } from '../lib/format'
import { errorMessages } from '../lib/errors'
import { STATUSES } from '../hooks/useStaffPayments'
import Button from './Button'

/** Putting a payment right by hand.
 *
 *  Deliberately unlike every other control on this screen. Dispatching and
 *  recording ask a provider or assert a bank statement; this overrules what a
 *  provider already said, so it is the one place a person's word beats the
 *  rails - and the reason is mandatory because the history is what somebody
 *  reads six months later when a customer disputes it.
 *
 *  Nothing is overwritten. The correction is another line in the payment's
 *  history, alongside the one it contradicts.
 */
function CorrectPaymentModal({ payment, mutation, onClose }) {
  const [status, setStatus] = useState(
    STATUSES.find(([value]) => value !== payment.status)?.[0] ?? 'paid',
  )
  const [reason, setReason] = useState('')

  const tooShort = reason.trim().length < 8

  function handleSubmit(event) {
    event.preventDefault()
    mutation.mutate(
      { reference: payment.reference, status, reason: reason.trim() },
      { onSuccess: onClose },
    )
  }

  return (
    <Modal onClose={onClose}>
      <h2 className="text-center font-serif text-section">Correct this payment</h2>

      <p className="mt-4 text-center text-meta leading-relaxed text-ink-soft">
        {formatPrice(payment.amount)} · {payment.method_label ?? payment.method} ·
        currently <span className="text-ink">{payment.status}</span>
      </p>

      <form onSubmit={handleSubmit} className="mt-8 space-y-6">
        <label className="block">
          <span className="text-badge uppercase text-ink-soft">
            It should be
          </span>
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            className="mt-3 h-12 w-full border border-line bg-surface px-3 text-model outline-none focus:border-ink"
          >
            {STATUSES.filter(([value]) => value !== payment.status).map(
              ([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ),
            )}
          </select>
        </label>

        <label className="block">
          <span className="text-badge uppercase text-ink-soft">Why</span>
          <textarea
            rows={3}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            className="mt-3 w-full border border-line bg-surface p-3 text-meta outline-none focus:border-ink"
          />
          <span className="mt-2 block text-meta text-ink-mute">
            Kept on the payment for good, with your name against it. "Fixed"
            tells whoever reads this next nothing.
          </span>
        </label>

        {mutation.isError && (
          <ul className="border border-line p-4">
            {errorMessages(mutation.error).map((message) => (
              <li key={message} className="text-meta leading-relaxed text-ink">
                {message}
              </li>
            ))}
          </ul>
        )}

        <div className="flex flex-wrap items-center justify-center gap-4">
          <Button
            type="submit"
            disabled={mutation.isPending || tooShort}
          >
            {mutation.isPending ? 'Saving' : 'Correct it'}
          </Button>
          <Button
            variant="quiet"
            onClick={onClose}
          >
            Cancel
          </Button>
        </div>
      </form>
    </Modal>
  )
}

export default CorrectPaymentModal
