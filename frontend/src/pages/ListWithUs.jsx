import { useState } from 'react'
import Button from '../components/Button'
import Page from '../components/Page'
import Section from '../components/Section'
import { errorMessages } from '../lib/errors'
import FilePicker from '../components/FilePicker'
import {
  DOCUMENT_KINDS,
  MAX_DOCUMENTS,
  MAX_PHOTOS,
  REQUIRED_DOCUMENTS,
  SELLER_TYPES,
  missingDocuments,
  useApplyToList,
} from '../hooks/useDealer'

/** A dealership asking to sell through Goldride.
 *
 *  Public, and deliberately the only door in: there is no "check my
 *  application" page, because the API cannot read applications back out. A
 *  list of who has approached us is a competitor's prospect list, so the
 *  endpoint is write-only and this page has nothing to poll.
 *
 *  It asks for a car, not just a dealership. Staff approving an application
 *  are approving that car onto the site in the same click, so the evidence has
 *  to be in front of them - the photographs a buyer will see, and the paperwork
 *  that says the car is theirs to sell.
 */

const fieldClass =
  'h-12 w-full border border-line bg-surface px-4 text-model outline-none focus:border-ink'
const labelClass = 'text-badge uppercase text-ink-soft'
const LABELS = Object.fromEntries(DOCUMENT_KINDS)

function ListWithUs() {
  const [values, setValues] = useState({
    seller_type: 'individual',
    dealership_name: '',
    id_number: '',
    contact_name: '',
    email: '',
    phone: '',
    location: '',
    fleet_size: '',
    message: '',
  })
  const [car, setCar] = useState({
    make: '',
    model: '',
    year: '',
    price: '',
    mileage_km: '',
    exterior_colour: '',
    description: '',
  })
  const [photos, setPhotos] = useState([])
  const [documents, setDocuments] = useState([])

  const apply = useApplyToList()
  const isDealership = values.seller_type === 'dealer'
  const missing = missingDocuments(values.seller_type, documents)

  function set(field) {
    return (event) =>
      setValues((current) => ({ ...current, [field]: event.target.value }))
  }

  function setCarField(field) {
    return (event) =>
      setCar((current) => ({ ...current, [field]: event.target.value }))
  }

  function handleSubmit(event) {
    event.preventDefault()
    apply.mutate({
      ...values,
      // An empty string is not a number, and DRF says so in a way nobody
      // wants to read on a form they have just filled in.
      fleet_size: values.fleet_size === '' ? null : Number(values.fleet_size),
      car,
      photos,
      documents,
    })
  }

  if (apply.isSuccess) {
    return (
      <Page>
        <div className="mx-auto max-w-[560px] border border-line bg-surface p-12 text-center">
          <h1 className="font-serif text-section">Thank you</h1>
          <p className="mt-4 text-model text-ink-soft">
            Your application is with our team, along with the{' '}
            {car.year} {car.make} {car.model}. We answer every one, usually
            within two working days, on {values.email}. If we take it on, the
            car goes on the site straight away and you get an account for
            anything you sell after that.
          </p>
          <Button to="/" variant="secondary" size="large" className="mt-8">
            Back to the cars
          </Button>
        </div>
      </Page>
    )
  }

  return (
    <Page>
      <div className="mx-auto max-w-[720px]">
        <h1 className="font-serif text-h1">List a car with Goldride</h1>
        <p className="mt-4 max-w-[560px] text-model text-ink-soft">
          We list cars from dealerships and private owners across Kenya
          alongside our own. Tell us who you are and about the car you would
          like listed. If we take it on, it goes on the site straight away and
          you get an account for anything you sell after that.
        </p>

        <form onSubmit={handleSubmit} className="mt-12">
          <Section
            first
            title="About you"
            note="Who we would be listing on behalf of, and how to reach you."
          >
          {/* First, because everything below it changes: a person is asked for
              an ID, a business for a trading name and a fleet. */}
          <fieldset>
            <legend className={labelClass}>Who is selling</legend>
            <div className="mt-3 flex flex-wrap gap-4">
              {SELLER_TYPES.map(([value, label]) => (
                <label
                  key={value}
                  className={`cursor-pointer border px-6 py-3 text-meta transition-colors ${
                    values.seller_type === value
                      ? 'border-ink bg-ink text-surface'
                      : 'border-line hover:border-line-hover'
                  }`}
                >
                  <input
                    type="radio"
                    name="seller_type"
                    value={value}
                    checked={values.seller_type === value}
                    onChange={set('seller_type')}
                    className="sr-only"
                  />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>

          <div className="grid gap-8 md:grid-cols-2">
            {isDealership ? (
              <label className="block">
                <span className={labelClass}>Dealership</span>
                <input
                  required
                  value={values.dealership_name}
                  onChange={set('dealership_name')}
                  className={`mt-3 ${fieldClass}`}
                />
              </label>
            ) : (
              <label className="block">
                <span className={labelClass}>ID or passport number</span>
                <input
                  required
                  value={values.id_number}
                  onChange={set('id_number')}
                  className={`mt-3 ${fieldClass}`}
                />
                <span className="mt-2 block text-meta text-ink-mute">
                  So we can check the car is yours to sell. Staff only.
                </span>
              </label>
            )}

            <label className="block">
              <span className={labelClass}>Your name</span>
              <input
                required
                value={values.contact_name}
                onChange={set('contact_name')}
                className={`mt-3 ${fieldClass}`}
              />
            </label>

            <label className="block">
              <span className={labelClass}>Email</span>
              <input
                required
                type="email"
                value={values.email}
                onChange={set('email')}
                className={`mt-3 ${fieldClass}`}
              />
            </label>

            <label className="block">
              <span className={labelClass}>Phone</span>
              <input
                required
                value={values.phone}
                onChange={set('phone')}
                className={`mt-3 ${fieldClass}`}
              />
            </label>

            <label className="block">
              <span className={labelClass}>Town or city</span>
              <input
                required
                value={values.location}
                onChange={set('location')}
                className={`mt-3 ${fieldClass}`}
              />
            </label>

            {isDealership && (
              <label className="block">
                <span className={labelClass}>Cars to sell</span>
                <input
                  type="number"
                  min="1"
                  value={values.fleet_size}
                  onChange={set('fleet_size')}
                  className={`mt-3 ${fieldClass}`}
                />
                <span className="mt-2 block text-meta text-ink-mute">
                  Roughly. It only tells us what to expect.
                </span>
              </label>
            )}
          </div>

          <label className="mt-8 block">
            <span className={labelClass}>Anything else</span>
            <textarea
              rows={5}
              value={values.message}
              onChange={set('message')}
              className="mt-3 w-full border border-line bg-surface p-4 text-model outline-none focus:border-ink"
            />
          </label>
          </Section>

          <Section
            title="The first car"
            note="The one you would like listed first. If we take you on, this car goes on the site straight away - so the price here is the price a buyer will see."
          >
            <div className="grid gap-8 md:grid-cols-2">
              <label className="block">
                <span className={labelClass}>Make</span>
                <input
                  required
                  value={car.make}
                  onChange={setCarField('make')}
                  className={`mt-3 ${fieldClass}`}
                />
              </label>

              <label className="block">
                <span className={labelClass}>Model</span>
                <input
                  required
                  value={car.model}
                  onChange={setCarField('model')}
                  className={`mt-3 ${fieldClass}`}
                />
              </label>

              <label className="block">
                <span className={labelClass}>Year</span>
                <input
                  required
                  type="number"
                  value={car.year}
                  onChange={setCarField('year')}
                  className={`mt-3 ${fieldClass}`}
                />
              </label>

              <label className="block">
                <span className={labelClass}>Asking price (KES)</span>
                <input
                  required
                  type="number"
                  min="1"
                  value={car.price}
                  onChange={setCarField('price')}
                  className={`mt-3 ${fieldClass}`}
                />
              </label>

              <label className="block">
                <span className={labelClass}>Mileage (km)</span>
                <input
                  type="number"
                  value={car.mileage_km}
                  onChange={setCarField('mileage_km')}
                  className={`mt-3 ${fieldClass}`}
                />
              </label>

              <label className="block">
                <span className={labelClass}>Colour</span>
                <input
                  value={car.exterior_colour}
                  onChange={setCarField('exterior_colour')}
                  className={`mt-3 ${fieldClass}`}
                />
              </label>
            </div>

            <label className="mt-8 block">
              <span className={labelClass}>About the car</span>
              <textarea
                rows={4}
                value={car.description}
                onChange={setCarField('description')}
                className="mt-3 w-full border border-line bg-surface p-4 text-model outline-none focus:border-ink"
              />
              <span className="mt-2 block text-meta text-ink-mute">
                Left blank, we write one from the details above.
              </span>
            </label>

            <div className="mt-10">
              <FilePicker
                label="Photographs"
                hint={`Up to ${MAX_PHOTOS}. The first becomes the main picture on the listing.`}
                accept="image/*"
                max={MAX_PHOTOS}
                files={photos}
                onChange={setPhotos}
                noun="photograph"
              />
            </div>

            <div className="mt-10">
              <FilePicker
                label="Paperwork"
                hint={
                  isDealership
                    ? 'What the dealer licensing process asks for. PDF or image, 10MB each. Only our staff ever see these.'
                    : 'Proof of who you are and that the car is yours to sell. PDF or image, 10MB each. Only our staff ever see these.'
                }
                accept=".pdf,image/*"
                max={MAX_DOCUMENTS}
                files={documents}
                onChange={setDocuments}
                labels={DOCUMENT_KINDS}
                noun="document"
                checklist={REQUIRED_DOCUMENTS[values.seller_type] ?? []}
              />
            </div>
          </Section>

          <div className="mt-16 border-t border-line pt-12">
          {apply.isError && (
            <ul className="border border-line bg-surface p-6">
              {errorMessages(apply.error).map((message) => (
                <li key={message} className="text-meta text-ink">
                  {message}
                </li>
              ))}
            </ul>
          )}

          <div>
            <Button
              size="large"
              type="submit"
              disabled={apply.isPending || missing.length > 0}
            >
              {apply.isPending ? 'Sending' : 'Send application'}
            </Button>

            {/* Said here as well as on the checklist: somebody who has scrolled
                past it needs to know why the button will not go. */}
            {missing.length > 0 && (
              <p className="mt-4 text-meta text-ink-soft">
                Still to attach: {missing.map((kind) => LABELS[kind]).join(', ')}.
              </p>
            )}
          </div>
          </div>
        </form>
      </div>
    </Page>
  )
}

export default ListWithUs
