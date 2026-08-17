import Modal from './Modal'
import { formatPrice } from '../lib/format'

/** The step in front of choosing a unit.
 *
 *  "Choose this one" does not say that it also declines every other unit we
 *  found, and nothing on this page can undo it afterwards. Worth one dialog.
 */
function ConfirmChoice({ unit, others, isPending, onCancel, onConfirm }) {
  return (
    <Modal onClose={onCancel}>
      <h2 className="text-center font-serif text-section">Confirm your choice</h2>

      <p className="mt-6 text-model text-ink">
        {unit.year} {unit.make} {unit.model}
      </p>
      <p className="text-price">{formatPrice(unit.total_kes)}</p>

      <p className="mt-6 border border-line p-4 text-meta leading-relaxed text-ink-soft">
        Choosing this unit declines the {others === 1 ? 'other one' : `other ${others}`} we
        found, and we will start the agreement on this car. You cannot change
        it from this page afterwards — call us if you need to.
      </p>

      <button
        type="button"
        disabled={isPending}
        onClick={onConfirm}
        className="mt-8 h-12 w-full bg-ink text-badge uppercase text-surface disabled:opacity-50"
      >
        {isPending ? 'Confirming...' : 'Yes, choose this one'}
      </button>
      <button
        type="button"
        onClick={onCancel}
        className="mt-3 h-12 w-full border border-ink text-badge uppercase"
      >
        Go back
      </button>
    </Modal>
  )
}

export default ConfirmChoice
