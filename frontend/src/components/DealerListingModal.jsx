import { useState } from 'react'
import Modal from './Modal'
import { errorMessages } from '../lib/errors'
import Button from './Button'

/** Submitting a car, or correcting one that came back.
 *
 *  Photographs are handled separately from the rest of the form, and only once
 *  the car exists: an upload needs an id to attach to, and asking a dealer to
 *  re-pick eight photographs because one field failed validation is the kind
 *  of thing that makes people give up and phone instead.
 */

const fieldClass =
  'h-11 w-full border border-line bg-surface px-3 text-model outline-none focus:border-ink'
const labelClass = 'text-badge uppercase text-ink-soft'

const FUELS = [
  ['', 'Not stated'],
  ['petrol', 'Petrol'],
  ['diesel', 'Diesel'],
  ['hybrid', 'Hybrid'],
  ['electric', 'Electric'],
]
const TRANSMISSIONS = [
  ['', 'Not stated'],
  ['automatic', 'Automatic'],
  ['manual', 'Manual'],
]
const BODIES = [
  ['', 'Not stated'],
  ['suv', 'SUV'],
  ['saloon', 'Saloon'],
  ['hatchback', 'Hatchback'],
  ['coupe', 'Coupe'],
  ['pickup', 'Pickup'],
  ['van', 'Van'],
  ['convertible', 'Convertible'],
]

function blank() {
  return {
    make: '',
    model: '',
    year: '',
    price: '',
    condition: 'used',
    mileage_km: '',
    fuel_type: '',
    transmission: '',
    body_type: '',
    exterior_colour: '',
    location: '',
    description: '',
  }
}

function Select({ label, value, onChange, options }) {
  return (
    <label className="block">
      <span className={labelClass}>{label}</span>
      <select value={value} onChange={onChange} className={`mt-2 ${fieldClass}`}>
        {options.map(([key, text]) => (
          <option key={key} value={key}>
            {text}
          </option>
        ))}
      </select>
    </label>
  )
}

function DealerListingModal({ listing, onClose, create, update, photos }) {
  const editing = Boolean(listing)
  const [values, setValues] = useState(() =>
    editing
      ? Object.fromEntries(
          Object.keys(blank()).map((key) => [key, listing[key] ?? '']),
        )
      : blank(),
  )

  const mutation = editing ? update : create
  const { addPhoto, removePhoto } = photos

  function set(field) {
    return (event) =>
      setValues((current) => ({ ...current, [field]: event.target.value }))
  }

  function handleSubmit(event) {
    event.preventDefault()
    const payload = {
      ...values,
      year: Number(values.year),
      mileage_km: values.mileage_km === '' ? null : Number(values.mileage_km),
    }
    if (editing) update.mutate({ id: listing.id, ...payload }, { onSuccess: onClose })
    else create.mutate(payload, { onSuccess: onClose })
  }

  return (
    <Modal onClose={onClose} size="dialog">
      <div className="p-8">
        <h2 className="font-serif text-section">
          {editing ? 'Edit this car' : 'Submit a car'}
        </h2>
        {editing && listing.status === 'rejected' && (
          <p className="mt-3 border border-line p-4 text-meta text-ink-soft">
            Sending this again puts it back in the queue.
            {listing.decision_note && ` Our note: ${listing.decision_note}`}
          </p>
        )}

        <form onSubmit={handleSubmit} className="mt-8 space-y-6">
          <div className="grid gap-6 sm:grid-cols-2">
            <label className="block">
              <span className={labelClass}>Make</span>
              <input
                required
                value={values.make}
                onChange={set('make')}
                className={`mt-2 ${fieldClass}`}
              />
            </label>
            <label className="block">
              <span className={labelClass}>Model</span>
              <input
                required
                value={values.model}
                onChange={set('model')}
                className={`mt-2 ${fieldClass}`}
              />
            </label>
            <label className="block">
              <span className={labelClass}>Year</span>
              <input
                required
                type="number"
                value={values.year}
                onChange={set('year')}
                className={`mt-2 ${fieldClass}`}
              />
            </label>
            <label className="block">
              <span className={labelClass}>Price (KES)</span>
              <input
                required
                type="number"
                min="1"
                value={values.price}
                onChange={set('price')}
                className={`mt-2 ${fieldClass}`}
              />
            </label>
            <label className="block">
              <span className={labelClass}>Mileage (km)</span>
              <input
                type="number"
                value={values.mileage_km}
                onChange={set('mileage_km')}
                className={`mt-2 ${fieldClass}`}
              />
            </label>
            <Select
              label="Condition"
              value={values.condition}
              onChange={set('condition')}
              options={[
                ['used', 'Used'],
                ['new', 'New'],
              ]}
            />
            <Select
              label="Fuel"
              value={values.fuel_type}
              onChange={set('fuel_type')}
              options={FUELS}
            />
            <Select
              label="Transmission"
              value={values.transmission}
              onChange={set('transmission')}
              options={TRANSMISSIONS}
            />
            <Select
              label="Body"
              value={values.body_type}
              onChange={set('body_type')}
              options={BODIES}
            />
            <label className="block">
              <span className={labelClass}>Colour</span>
              <input
                value={values.exterior_colour}
                onChange={set('exterior_colour')}
                className={`mt-2 ${fieldClass}`}
              />
            </label>
          </div>

          <label className="block">
            <span className={labelClass}>Where the car is</span>
            <input
              value={values.location}
              onChange={set('location')}
              className={`mt-2 ${fieldClass}`}
            />
          </label>

          <label className="block">
            <span className={labelClass}>Description</span>
            <textarea
              rows={4}
              value={values.description}
              onChange={set('description')}
              className="mt-2 w-full border border-line bg-surface p-3 text-model outline-none focus:border-ink"
            />
            <span className="mt-2 block text-meta text-ink-mute">
              Left blank, we write one from the details above.
            </span>
          </label>

          {mutation.isError && (
            <ul className="border border-line p-4">
              {errorMessages(mutation.error).map((message) => (
                <li key={message} className="text-meta text-ink">
                  {message}
                </li>
              ))}
            </ul>
          )}

          <div className="flex flex-wrap items-center gap-4 border-t border-line pt-6">
            <Button
              type="submit"
              disabled={mutation.isPending}
            >
              {mutation.isPending
                ? 'Saving'
                : editing
                  ? 'Save and resend'
                  : 'Submit for review'}
            </Button>
            <Button
              variant="quiet"
              onClick={onClose}
            >
              Cancel
            </Button>
          </div>
        </form>

        {/* Only once the car exists - an upload needs something to attach to. */}
        {editing && (
          <section className="mt-10 border-t border-line pt-8">
            <h3 className="text-badge uppercase text-ink-soft">Photographs</h3>
            <p className="mt-2 text-meta text-ink-mute">
              The first one becomes the main picture on the listing.
            </p>

            <ul className="mt-6 flex flex-wrap gap-4">
              {listing.images.map((image) => (
                <li key={image.id} className="relative">
                  <img
                    src={image.image}
                    alt=""
                    loading="eager"
                    className="h-24 w-32 border border-line object-cover"
                  />
                  <Button
                    variant="quiet"
                    className="mt-2"
                    onClick={() =>
                      removePhoto.mutate({ id: listing.id, imageId: image.id })
                    }
                  >
                    Remove
                  </Button>
                </li>
              ))}
            </ul>

            <label className="mt-6 inline-block cursor-pointer border border-ink px-6 py-3 text-badge uppercase">
              {addPhoto.isPending ? 'Uploading' : 'Add a photograph'}
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0]
                  if (file) addPhoto.mutate({ id: listing.id, file })
                  // Cleared so the same file can be picked again after a
                  // failure - otherwise onChange never fires a second time.
                  event.target.value = ''
                }}
              />
            </label>
          </section>
        )}
      </div>
    </Modal>
  )
}

export default DealerListingModal
