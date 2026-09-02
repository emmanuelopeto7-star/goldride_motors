import Modal from './Modal'
import { errorMessages } from '../lib/errors'
import Button from './Button'

/** Are you sure - for the handful of things that cannot be undone.
 *
 *  It stays open when the mutation fails, because the interesting refusals
 *  here are not "something went wrong" but reasons: a car cannot be deleted
 *  while purchase requests point at it, an order cannot while it holds
 *  payments. Closing on error would throw that explanation away.
 */
function ConfirmModal({
  title,
  body,
  confirmLabel = 'Delete it',
  mutation,
  onConfirm,
  onClose,
}) {
  return (
    <Modal onClose={onClose}>
      <h2 className="text-center font-serif text-section">{title}</h2>

      <p className="mt-4 text-center text-meta leading-relaxed text-ink-soft">
        {body}
      </p>

      {mutation?.isError && (
        <ul className="mt-6 border border-line p-4">
          {errorMessages(mutation.error).map((message) => (
            <li key={message} className="text-meta leading-relaxed text-ink">
              {message}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-8 flex flex-wrap gap-3">
        <Button
          size="large"
          className="flex-1"
          disabled={mutation?.isPending}
          onClick={onConfirm}
        >
          {mutation?.isPending ? 'Working...' : confirmLabel}
        </Button>
        <Button
          variant="secondary"
          size="large"
          className="flex-1"
          onClick={onClose}
        >
          Keep it
        </Button>
      </div>
    </Modal>
  )
}

export default ConfirmModal
