import Modal from './Modal'
import { formatPrice } from '../lib/format'
import Button from './Button'

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

      <Button
        size="large"
        className="mt-8 w-full"
        disabled={isPending}
        onClick={onConfirm}
      >
        {isPending ? 'Confirming...' : 'Yes, choose this one'}
      </Button>
      <Button
        variant="secondary"
        size="large"
        className="mt-3 w-full"
        onClick={onCancel}
      >
        Go back
      </Button>
    </Modal>
  )
}

export default ConfirmChoice
