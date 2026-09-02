import { useState } from 'react'
import Modal from './Modal'
import { errorMessages } from '../lib/errors'
import Button from './Button'

const fieldClass =
  'h-12 w-full border border-line bg-surface px-4 text-model outline-none focus:border-ink'
const labelClass = 'text-badge uppercase text-ink-soft'

/** The fields that actually change after a listing goes up.
 *
 *  Not a full editor. Price, availability, chassis and the walkthrough link
 *  are what staff revisit; make, model and year are wrong far less often than
 *  they are mistyped in a hurry, so they stay in the admin.
 */
function CarEditModal({ car, mutation, onClose }) {
  const [values, setValues] = useState({
    price: car.price ?? '',
    availability: car.availability ?? 'available',
    vin: car.vin ?? '',
    video_url: car.video_url ?? '',
  })

  function set(field) {
    return (event) =>
      setValues((current) => ({ ...current, [field]: event.target.value }))
  }

  function handleSubmit(event) {
    event.preventDefault()
    mutation.mutate({ id: car.id, ...values }, { onSuccess: onClose })
  }

  return (
    <Modal onClose={onClose}>
      <h2 className="text-center font-serif text-section">Edit listing</h2>
      <p className="mt-2 text-center text-meta text-ink-soft">
        {car.year} {car.make} {car.model}
      </p>

      <form onSubmit={handleSubmit} className="mt-8">
        <div>
          <label htmlFor="e-price" className={labelClass}>Price (KES)</label>
          <input
            id="e-price"
            type="number"
            step="0.01"
            required
            value={values.price}
            onChange={set('price')}
            className={`mt-2 ${fieldClass}`}
          />
        </div>

        <div className="mt-6">
          <label htmlFor="e-availability" className={labelClass}>Availability</label>
          <select
            id="e-availability"
            value={values.availability}
            onChange={set('availability')}
            className={`mt-2 ${fieldClass}`}
          >
            <option value="available">Available</option>
            <option value="reserved">Reserved</option>
            <option value="sold">Sold</option>
          </select>
        </div>

        <div className="mt-6">
          <label htmlFor="e-vin" className={labelClass}>VIN / chassis</label>
          <input
            id="e-vin"
            maxLength={17}
            value={values.vin}
            onChange={set('vin')}
            className={`mt-2 ${fieldClass}`}
          />
          <p className="mt-2 text-meta text-ink-mute">
            Must be unique across listings — it is what stops the same car
            being listed twice.
          </p>
        </div>

        <div className="mt-6">
          <label htmlFor="e-video" className={labelClass}>Walkthrough video</label>
          <input
            id="e-video"
            type="url"
            value={values.video_url}
            onChange={set('video_url')}
            placeholder="https://youtu.be/..."
            className={`mt-2 ${fieldClass}`}
          />
          <p className="mt-2 text-meta text-ink-mute">YouTube or Vimeo only.</p>
        </div>

        {mutation.isError && (
          <ul className="mt-6">
            {errorMessages(mutation.error).map((message) => (
              <li key={message} className="text-meta text-ink">{message}</li>
            ))}
          </ul>
        )}

        <Button
          size="large"
          className="mt-8 w-full"
          type="submit"
          disabled={mutation.isPending}
        >
          {mutation.isPending ? 'Saving...' : 'Save'}
        </Button>
      </form>
    </Modal>
  )
}

export default CarEditModal
