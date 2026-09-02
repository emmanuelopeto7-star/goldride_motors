import { useState } from 'react'
import Modal from './Modal'
import { errorMessages } from '../lib/errors'
import Button from './Button'

const fieldClass =
  'h-12 w-full border border-line bg-surface px-4 text-model outline-none focus:border-ink'
const labelClass = 'text-badge uppercase text-ink-soft'

const BODY_TYPES = [
  ['suv', 'SUV'],
  ['saloon', 'Saloon'],
  ['hatchback', 'Hatchback'],
  ['coupe', 'Coupe'],
  ['pickup', 'Pickup'],
  ['van', 'Van'],
  ['convertible', 'Convertible'],
]
const FUELS = [
  ['petrol', 'Petrol'],
  ['diesel', 'Diesel'],
  ['hybrid', 'Hybrid'],
  ['electric', 'Electric'],
]
const TRANSMISSIONS = [
  ['automatic', 'Automatic'],
  ['manual', 'Manual'],
]
const DRIVETRAINS = [
  ['2wd', '2WD'],
  ['awd', 'AWD'],
  ['4wd', '4WD'],
]

function Field({ id, label, hint, ...props }) {
  return (
    <div>
      <label htmlFor={id} className={labelClass}>{label}</label>
      <input id={id} className={`mt-2 ${fieldClass}`} {...props} />
      {hint && <p className="mt-2 text-meta text-ink-mute">{hint}</p>}
    </div>
  )
}

/** `blank` is off for condition and availability: those are not optional -
 *  they have real defaults on the model - and offering "Not stated" for them
 *  invites an answer the catalogue cannot show. */
function Select({ id, label, options, value, onChange, blank = true }) {
  return (
    <div>
      <label htmlFor={id} className={labelClass}>{label}</label>
      <select id={id} value={value} onChange={onChange} className={`mt-2 ${fieldClass}`}>
        {blank && <option value="">Not stated</option>}
        {options.map(([key, text]) => (
          <option key={key} value={key}>{text}</option>
        ))}
      </select>
    </div>
  )
}

/** Adding a car to the catalogue.
 *
 *  The spec sheet is here rather than left for a second pass because the
 *  storefront filters on it: a listing with no body type or fuel matches
 *  none of the filters buyers actually use, so it may as well not be listed.
 *  All of it stays optional, though - a car gets listed before every figure
 *  is confirmed, and the detail page omits whatever is blank.
 */
function CarCreateModal({ mutation, onClose, onCreated }) {
  const [values, setValues] = useState({
    make: '',
    model: '',
    year: '',
    price: '',
    description: '',
    condition: 'used',
    availability: 'available',
    mileage_km: '',
    engine_cc: '',
    fuel_type: '',
    transmission: '',
    drivetrain: '',
    body_type: '',
    exterior_colour: '',
    interior_colour: '',
    location: '',
    vin: '',
    image: null,
  })

  function set(field) {
    return (event) =>
      setValues((current) => ({ ...current, [field]: event.target.value }))
  }

  function handleSubmit(event) {
    event.preventDefault()
    mutation.mutate(values, {
      onSuccess: (car) => {
        // Straight into the photographs: a listing with a blank card is the
        // catalogue's biggest problem, and the moment right after creating
        // one is when the pictures are to hand.
        onCreated?.(car)
        onClose()
      },
    })
  }

  return (
    <Modal onClose={onClose}>
      <h2 className="text-center font-serif text-section">Add a listing</h2>

      <form onSubmit={handleSubmit} className="mt-8">
        <fieldset>
          <legend className={labelClass}>The car</legend>
          <div className="mt-4 grid gap-6 sm:grid-cols-2">
            <Field id="c-make" label="Make" required value={values.make} onChange={set('make')} placeholder="Toyota" />
            <Field id="c-model" label="Model" required value={values.model} onChange={set('model')} placeholder="Land Cruiser" />
            <Field id="c-year" label="Year" type="number" required value={values.year} onChange={set('year')} />
            <Field id="c-price" label="Price (KES)" type="number" step="0.01" required value={values.price} onChange={set('price')} />
            <Select id="c-condition" label="Condition" blank={false} options={[['used', 'Used'], ['new', 'New']]} value={values.condition} onChange={set('condition')} />
            <Select id="c-availability" label="Availability" blank={false} options={[['available', 'Available'], ['reserved', 'Reserved'], ['sold', 'Sold']]} value={values.availability} onChange={set('availability')} />
          </div>

          <div className="mt-6">
            <label htmlFor="c-description" className={labelClass}>Description</label>
            <textarea
              id="c-description"
              rows={4}
              required
              value={values.description}
              onChange={set('description')}
              placeholder="Imported, one owner, full service history."
              className="mt-2 w-full border border-line bg-surface p-4 text-meta leading-relaxed"
            />
          </div>
        </fieldset>

        <fieldset className="mt-10 border-t border-line pt-8">
          <legend className={labelClass}>The spec</legend>
          <p className="mt-2 text-meta text-ink-mute">
            Buyers filter on these. Anything left blank is simply omitted.
          </p>
          <div className="mt-4 grid gap-6 sm:grid-cols-2">
            <Select id="c-body" label="Body" options={BODY_TYPES} value={values.body_type} onChange={set('body_type')} />
            <Select id="c-fuel" label="Fuel" options={FUELS} value={values.fuel_type} onChange={set('fuel_type')} />
            <Select id="c-gearbox" label="Gearbox" options={TRANSMISSIONS} value={values.transmission} onChange={set('transmission')} />
            <Select id="c-drive" label="Drivetrain" options={DRIVETRAINS} value={values.drivetrain} onChange={set('drivetrain')} />
            <Field id="c-mileage" label="Mileage (km)" type="number" min="0" value={values.mileage_km} onChange={set('mileage_km')} />
            <Field id="c-engine" label="Engine (cc)" type="number" min="0" value={values.engine_cc} onChange={set('engine_cc')} />
            <Field id="c-exterior" label="Exterior colour" value={values.exterior_colour} onChange={set('exterior_colour')} />
            <Field id="c-interior" label="Interior colour" value={values.interior_colour} onChange={set('interior_colour')} />
            <Field id="c-location" label="Location" value={values.location} onChange={set('location')} placeholder="Nairobi, Kenya" />
            <Field id="c-vin" label="Chassis / VIN" value={values.vin} onChange={set('vin')} />
          </div>
        </fieldset>

        <fieldset className="mt-10 border-t border-line pt-8">
          <legend className={labelClass}>The photograph</legend>
          <input
            id="c-image"
            type="file"
            accept="image/*"
            onChange={(event) =>
              setValues((current) => ({
                ...current,
                image: event.target.files[0] ?? null,
              }))
            }
            className="mt-4 w-full border border-line bg-surface p-3 text-meta"
          />
          <p className="mt-2 text-meta text-ink-mute">
            The card image. You can add the rest of the gallery straight after.
          </p>
        </fieldset>

        {mutation.isError && (
          <ul className="mt-8">
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
          {mutation.isPending ? 'Adding...' : 'Add to inventory'}
        </Button>
      </form>
    </Modal>
  )
}

export default CarCreateModal
