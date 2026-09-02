import { useState } from 'react'
import { Link } from 'react-router-dom'
import Page from '../components/Page'
import { errorMessages } from '../lib/errors'
import { useAuth } from '../context/AuthContext'
import {
  MAX_VEHICLE_AGE_YEARS,
  earliestEligibleYear,
  useCreateImportRequest,
} from '../hooks/useImportRequest'
import Button from '../components/Button'

const fieldClass =
  'h-12 w-full border border-line bg-surface px-4 text-model outline-none focus:border-ink'
const labelClass = 'text-badge uppercase text-ink-soft'

function ImportRequest() {
  const { user } = useAuth()
  const oldest = earliestEligibleYear()

  const [values, setValues] = useState({
    contact_name: user?.username ?? '',
    email: user?.email ?? '',
    phone: '',
    make: '',
    model: '',
    year: '',
    budget_kes: '',
    notes: '',
  })

  const create = useCreateImportRequest()

  function set(field) {
    return (event) =>
      setValues((current) => ({ ...current, [field]: event.target.value }))
  }

  // Checked as they type rather than only on submit. The server refuses it
  // either way, but finding out after filling in eight fields is a worse way
  // to learn that your car is too old to import.
  const year = Number(values.year)
  const yearIneligible = values.year !== '' && year < oldest

  function handleSubmit(event) {
    event.preventDefault()
    create.mutate({
      ...values,
      budget_kes: values.budget_kes || null,
    })
  }

  if (create.isSuccess) {
    const token = create.data.token
    return (
      <Page>
        <h1 className="font-serif text-h1">We are looking</h1>
        <p className="mt-4 max-w-[68ch] text-model leading-relaxed text-ink-soft">
          Your request for a {create.data.year} {create.data.make}{' '}
          {create.data.model} is with our sourcing team. We will email you as
          soon as we have units to show you, usually within a few days.
        </p>
        <p className="mt-8 max-w-[68ch] text-model leading-relaxed text-ink-soft">
          Keep this link. It is how you come back to your request and choose
          between the units we find.
        </p>
        <Link
          to={`/imports/${token}`}
          className="mt-4 inline-block break-all text-meta text-ink underline"
        >
          {window.location.origin}/imports/{token}
        </Link>
      </Page>
    )
  }

  return (
    <Page>
      <h1 className="font-serif text-h1">Import a car</h1>
      <p className="mt-4 max-w-[68ch] text-model leading-relaxed text-ink-soft">
        Tell us what you are looking for and we will source it from Japan. You
        will see each unit we find with its full cost breakdown — landed,
        cleared and delivered — before you commit to anything.
      </p>

      <form onSubmit={handleSubmit} className="mt-12 max-w-[560px]">
        <fieldset>
          <legend className="font-serif text-section">The car</legend>

          <div className="mt-6 grid gap-6 sm:grid-cols-2">
            <div>
              <label htmlFor="make" className={labelClass}>Make</label>
              <input
                id="make"
                required
                value={values.make}
                onChange={set('make')}
                placeholder="Toyota"
                className={`mt-2 ${fieldClass}`}
              />
            </div>
            <div>
              <label htmlFor="model" className={labelClass}>Model</label>
              <input
                id="model"
                required
                value={values.model}
                onChange={set('model')}
                placeholder="Land Cruiser Prado"
                className={`mt-2 ${fieldClass}`}
              />
            </div>
          </div>

          <div className="mt-6 grid gap-6 sm:grid-cols-2">
            <div>
              <label htmlFor="year" className={labelClass}>Year</label>
              <input
                id="year"
                type="number"
                required
                min={oldest}
                max={new Date().getFullYear()}
                value={values.year}
                onChange={set('year')}
                placeholder={String(oldest + 2)}
                aria-describedby="year-rule"
                className={`mt-2 ${fieldClass}`}
              />
              <p id="year-rule" className="mt-2 text-meta text-ink-soft">
                {yearIneligible ? (
                  <span className="text-ink">
                    Too old to clear. Kenya will not admit a vehicle over{' '}
                    {MAX_VEHICLE_AGE_YEARS} years, so {oldest} is the oldest we
                    can import this year.
                  </span>
                ) : (
                  `${oldest} or newer — Kenya will not clear anything older.`
                )}
              </p>
            </div>
            <div>
              <label htmlFor="budget" className={labelClass}>
                Budget (KES, optional)
              </label>
              <input
                id="budget"
                type="number"
                min="0"
                value={values.budget_kes}
                onChange={set('budget_kes')}
                placeholder="4500000"
                className={`mt-2 ${fieldClass}`}
              />
            </div>
          </div>

          <div className="mt-6">
            <label htmlFor="notes" className={labelClass}>
              Anything specific? (optional)
            </label>
            <textarea
              id="notes"
              rows={3}
              value={values.notes}
              onChange={set('notes')}
              placeholder="Colour, trim, mileage, must-have options"
              className="mt-2 w-full border border-line bg-surface p-4 text-model outline-none focus:border-ink"
            />
          </div>
        </fieldset>

        <fieldset className="mt-12 border-t border-line pt-12">
          <legend className="font-serif text-section">How to reach you</legend>

          <div className="mt-6">
            <label htmlFor="contact_name" className={labelClass}>Name</label>
            <input
              id="contact_name"
              required
              value={values.contact_name}
              onChange={set('contact_name')}
              className={`mt-2 ${fieldClass}`}
            />
          </div>

          <div className="mt-6 grid gap-6 sm:grid-cols-2">
            <div>
              <label htmlFor="email" className={labelClass}>Email</label>
              <input
                id="email"
                type="email"
                required
                value={values.email}
                onChange={set('email')}
                className={`mt-2 ${fieldClass}`}
              />
            </div>
            <div>
              <label htmlFor="phone" className={labelClass}>Phone</label>
              <input
                id="phone"
                required
                value={values.phone}
                onChange={set('phone')}
                placeholder="0712 345 678"
                className={`mt-2 ${fieldClass}`}
              />
            </div>
          </div>

          {/* No account needed. Saying so removes the commonest reason
              someone abandons a form like this one. */}
          {!user && (
            <p className="mt-6 text-meta text-ink-soft">
              No account needed — we will email you a link to your request.
            </p>
          )}
        </fieldset>

        {create.isError && (
          <ul className="mt-8">
            {errorMessages(create.error).map((message) => (
              <li key={message} className="text-meta text-ink">
                {message}
              </li>
            ))}
          </ul>
        )}

        <Button
          size="large"
          className="mt-12 w-full sm:w-auto sm:px-12"
          type="submit"
          disabled={create.isPending || yearIneligible}
        >
          {create.isPending ? 'Sending...' : 'Start the search'}
        </Button>
      </form>
    </Page>
  )
}

export default ImportRequest
