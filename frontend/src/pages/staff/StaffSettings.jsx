import { useState } from 'react'
import ErrorState from '../../components/ErrorState'
import TeamSection from '../../components/TeamSection'
import { errorMessages } from '../../lib/errors'
import { useAuth } from '../../context/AuthContext'
import { useImportRates, useSetImportRates } from '../../hooks/useSourcing'
import Button from '../../components/Button'

const fieldClass =
  'h-12 w-full border border-line bg-surface px-4 text-model outline-none focus:border-ink'
const labelClass = 'text-badge uppercase text-ink-soft'

function Field({ id, label, hint, ...props }) {
  return (
    <div>
      <label htmlFor={id} className={labelClass}>{label}</label>
      <input id={id} className={`mt-2 ${fieldClass}`} {...props} />
      {hint && <p className="mt-2 text-meta text-ink-mute">{hint}</p>}
    </div>
  )
}

/** The KRA percentages the landing-cost calculator runs on.
 *
 *  Putting new ones in force adds a row rather than editing one: every quote
 *  copies the rates it was worked out under onto itself, and overwriting them
 *  would leave old quotes showing figures nobody could account for.
 */
function RatesSection() {
  const { data: rates, isPending, isError, refetch } = useImportRates()
  const setRates = useSetImportRates()
  const { isManager } = useAuth()
  const [editing, setEditing] = useState(false)
  const [values, setValues] = useState(null)

  function open() {
    setRates.reset()
    setValues({
      duty_rate: rates.duty,
      excise_rate: rates.excise_default,
      vat_rate: rates.vat,
      idf_rate: rates.idf,
      rdl_rate: rates.rdl,
      stock_markup: rates.stock_markup,
      effective_from: new Date().toISOString().slice(0, 10),
      note: '',
    })
    setEditing(true)
  }

  function set(field) {
    return (event) =>
      setValues((current) => ({ ...current, [field]: event.target.value }))
  }

  if (isPending) return <div className="h-32 w-full animate-pulse bg-line" />
  if (isError) {
    return <ErrorState message="We could not load the rates." onRetry={refetch} />
  }

  const shown = [
    ['Import duty', rates.duty],
    ['Excise (default)', rates.excise_default],
    ['VAT', rates.vat],
    ['IDF', rates.idf],
    ['Railway development levy', rates.rdl],
    ['Stock markup', rates.stock_markup],
  ]

  return (
    <section className="mt-16 border-t border-line pt-12">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="font-serif text-section">Import rates</h2>
          <p className="mt-1 text-meta text-ink-soft">
            In force since{' '}
            {new Date(rates.effective_from).toLocaleDateString('en-KE')}. Every
            sourcing quote is worked out on these.
          </p>
        </div>
        {isManager && !editing && (
          <Button
            variant="secondary"
            onClick={open}
          >
            Put new rates in force
          </Button>
        )}
      </div>

      <dl className="mt-6 grid gap-x-12 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
        {shown.map(([label, value]) => (
          <div key={label} className="flex justify-between border-b border-line py-2 text-meta">
            <dt className="text-ink-soft">{label}</dt>
            <dd>{value}%</dd>
          </div>
        ))}
      </dl>

      {!isManager && (
        <p className="mt-4 text-meta text-ink-mute">
          Only a Manager can change these.
        </p>
      )}

      {editing && values && (
        <form
          onSubmit={(event) => {
            event.preventDefault()
            setRates.mutate(values, { onSuccess: () => setEditing(false) })
          }}
          className="mt-8 border border-line bg-surface p-6"
        >
          <p className="text-meta text-ink-soft">
            This adds a new set rather than editing the old one. Quotes already
            given keep the rates they were worked out under.
          </p>

          <div className="mt-6 grid gap-6 sm:grid-cols-3">
            <Field id="r-duty" label="Import duty (%)" type="number" step="0.01" required value={values.duty_rate} onChange={set('duty_rate')} />
            <Field id="r-excise" label="Excise (%)" type="number" step="0.01" required value={values.excise_rate} onChange={set('excise_rate')} hint="Starting point - it is banded per unit." />
            <Field id="r-vat" label="VAT (%)" type="number" step="0.01" required value={values.vat_rate} onChange={set('vat_rate')} />
            <Field id="r-idf" label="IDF (%)" type="number" step="0.01" required value={values.idf_rate} onChange={set('idf_rate')} />
            <Field id="r-rdl" label="RDL (%)" type="number" step="0.01" required value={values.rdl_rate} onChange={set('rdl_rate')} />
            <Field id="r-markup" label="Stock markup (%)" type="number" step="0.01" required value={values.stock_markup} onChange={set('stock_markup')} />
            <Field id="r-from" label="In force from" type="date" required value={values.effective_from} onChange={set('effective_from')} />
            <div className="sm:col-span-2">
              <Field id="r-note" label="Where these came from" value={values.note} onChange={set('note')} placeholder="Finance Act 2026" />
            </div>
          </div>

          {setRates.isError && (
            <ul className="mt-6">
              {errorMessages(setRates.error).map((message) => (
                <li key={message} className="text-meta text-ink">{message}</li>
              ))}
            </ul>
          )}

          <div className="mt-6 flex flex-wrap gap-3">
            <Button
              size="large"
              type="submit"
              disabled={setRates.isPending}
            >
              {setRates.isPending ? 'Saving...' : 'Put them in force'}
            </Button>
            <Button
              variant="secondary"
              size="large"
              onClick={() => setEditing(false)}
            >
              Cancel
            </Button>
          </div>
        </form>
      )}
    </section>
  )
}

/** Everything that used to need the Django admin. */
function StaffSettings() {
  const { isManager } = useAuth()

  return (
    <div>
      <RatesSection />
      {/* Staff accounts are a manager's business only - the API refuses Sales
          outright, so the section is not rendered rather than rendered and
          then refused. */}
      {isManager && <TeamSection />}
    </div>
  )
}

export default StaffSettings
