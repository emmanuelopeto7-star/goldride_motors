import { useState } from 'react'
import Modal from './Modal'
import { errorMessages } from '../lib/errors'
import { formatPrice } from '../lib/format'
import { describeApproval } from '../hooks/usePurchaseRequests'
import Button from './Button'

/** The confirm step in front of a decision, and the report afterwards.
 *
 *  Approving is not a status flip - it creates the import order, reserves the
 *  car, raises the payment and dispatches collection, none of which can be
 *  undone from this screen. That earns a confirm rather than a bare button.
 *
 *  The outcome stays on screen until dismissed because it can carry a checkout
 *  URL that exists nowhere else in the UI, and because "approved but you must
 *  collect this by bank transfer" is a sentence someone has to actually read.
 */
function ApprovalDecisionModal({ action, request, onClose, mutation }) {
  const [note, setNote] = useState('')
  const approving = action === 'approve'
  const result = mutation.data

  function handleSubmit(event) {
    event.preventDefault()
    mutation.mutate({ id: request.id, note })
  }

  if (result) {
    const outcome = approving
      ? describeApproval(result)
      : { tone: 'done', message: 'Request rejected.' }

    return (
      <Modal onClose={onClose}>
        <h2 className="text-center font-serif text-section">
          {approving ? 'Approved' : 'Rejected'}
        </h2>

        <p className="mt-6 text-model leading-relaxed text-ink-soft">
          {outcome.message}
        </p>

        {outcome.checkoutUrl && (
          <a
            href={outcome.checkoutUrl}
            target="_blank"
            rel="noreferrer"
            // §2.1: black and underlined, never coloured.
            className="mt-6 block break-all text-meta text-ink underline"
          >
            {outcome.checkoutUrl}
          </a>
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
      <h2 className="text-center font-serif text-section">
        {approving ? 'Approve request' : 'Reject request'}
      </h2>

      <p className="mt-6 text-model text-ink">{request.car_title}</p>
      <p className="text-price">{formatPrice(request.price)}</p>
      <p className="mt-1 text-meta text-ink-soft">
        {request.customer_username} · {request.phone}
      </p>

      {approving && (
        <p className="mt-6 border border-line p-4 text-meta leading-relaxed text-ink-soft">
          This creates the import order, reserves the car, raises the payment
          and sends the customer a way to pay. It cannot be undone here.
        </p>
      )}

      <form onSubmit={handleSubmit} className="mt-6">
        <label htmlFor="decision-note" className="text-badge uppercase text-ink-soft">
          Note {approving ? '(optional)' : '- the customer sees this'}
        </label>
        <textarea
          id="decision-note"
          value={note}
          onChange={(event) => setNote(event.target.value)}
          rows={3}
          maxLength={200}
          className="mt-2 w-full border border-line bg-surface p-3 text-meta outline-none focus:border-ink"
        />

        {mutation.isError && (
          <ul className="mt-4">
            {errorMessages(mutation.error).map((message) => (
              <li key={message} className="text-meta text-ink">
                {message}
              </li>
            ))}
          </ul>
        )}

        <Button
          type="submit"
          variant={approving ? 'primary' : 'secondary'}
          size="large"
          className="mt-6 w-full"
          disabled={mutation.isPending}
        >
          {mutation.isPending
            ? 'Working...'
            : approving
              ? 'Approve and collect'
              : 'Reject'}
        </Button>
      </form>
    </Modal>
  )
}

export default ApprovalDecisionModal
