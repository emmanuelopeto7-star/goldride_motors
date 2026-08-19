import { useState } from 'react'
import Modal from './Modal'
import { errorMessages } from '../lib/errors'
import { STAGES, nextStage } from '../hooks/useStaffOrders'

const labelClass = 'text-badge uppercase text-ink-soft'

/** Move an order along, and say something useful while doing it.
 *
 *  The note is what the customer reads on their tracking page - "cleared
 *  Mombasa, on the road Thursday" is the difference between a status page and
 *  a status page worth checking. It is optional because a stage with no note
 *  still beats no update at all.
 */
function AdvanceStageModal({ order, mutation, onClose }) {
  const suggested = nextStage(order.current_stage)
  const [stage, setStage] = useState(suggested?.[0] ?? order.current_stage)
  const [note, setNote] = useState('')

  function handleSubmit(event) {
    event.preventDefault()
    mutation.mutate({ orderId: order.id, stage, note }, { onSuccess: onClose })
  }

  return (
    <Modal onClose={onClose}>
      <h2 className="text-center font-serif text-section">Update progress</h2>
      <p className="mt-2 text-center text-meta text-ink-soft">
        {order.car_description}
      </p>

      <form onSubmit={handleSubmit} className="mt-8">
        <label htmlFor="stage" className={labelClass}>Stage</label>
        <select
          id="stage"
          value={stage}
          onChange={(event) => setStage(event.target.value)}
          className="mt-2 h-12 w-full border border-line bg-surface px-4 text-model outline-none focus:border-ink"
        >
          {STAGES.map(([key, label]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>

        {stage === 'delivered' && (
          <p className="mt-4 border border-ink p-4 text-meta leading-relaxed">
            Marking this delivered also marks the car sold. It will stop
            appearing as available on the site.
          </p>
        )}

        <div className="mt-6">
          <label htmlFor="note" className={labelClass}>
            Note (the customer sees this)
          </label>
          <textarea
            id="note"
            rows={3}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Cleared Mombasa, on the road Thursday"
            className="mt-2 w-full border border-line bg-surface p-3 text-meta outline-none focus:border-ink"
          />
        </div>

        {mutation.isError && (
          <ul className="mt-4">
            {errorMessages(mutation.error).map((message) => (
              <li key={message} className="text-meta text-ink">{message}</li>
            ))}
          </ul>
        )}

        <button
          type="submit"
          disabled={mutation.isPending}
          className="mt-8 h-12 w-full bg-ink text-badge uppercase text-surface disabled:opacity-50"
        >
          {mutation.isPending ? 'Saving...' : 'Record this update'}
        </button>
      </form>
    </Modal>
  )
}

export default AdvanceStageModal
