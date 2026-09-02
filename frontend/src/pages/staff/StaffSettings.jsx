import { useState } from 'react'
import ErrorState from '../../components/ErrorState'
import TeamSection from '../../components/TeamSection'
import { errorMessages } from '../../lib/errors'
import { useAuth } from '../../context/AuthContext'
import { useHeroBanners } from '../../hooks/useHeroBanners'
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

/** The home page hero.
 *
 *  Several banners can be active at once and only the most recently updated
 *  one is served, so the list says outright which is on the site rather than
 *  leaving that rule to be remembered.
 */
function HeroSection() {
  const { query, create, update, remove } = useHeroBanners()
  const { isManager } = useAuth()
  const [adding, setAdding] = useState(false)
  const [values, setValues] = useState({
    headline: '',
    subline: '',
    cta_label: '',
    cta_url: '',
    is_active: true,
    image: null,
    video: null,
  })

  function set(field) {
    return (event) =>
      setValues((current) => ({ ...current, [field]: event.target.value }))
  }

  function handleSubmit(event) {
    event.preventDefault()
    create.mutate(values, {
      onSuccess: () => {
        setAdding(false)
        setValues({
          headline: '', subline: '', cta_label: '', cta_url: '',
          is_active: true, image: null, video: null,
        })
      },
    })
  }

  const banners = query.data ?? []

  return (
    <section>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="font-serif text-section">Home page hero</h2>
          <p className="mt-1 text-meta text-ink-soft">
            The full-bleed image at the top of the shopfront.
          </p>
        </div>
        <Button
          variant="secondary"
          onClick={() => {
            create.reset()
            setAdding((open) => !open)
          }}
        >
          {adding ? 'Cancel' : 'Add a hero'}
        </Button>
      </div>

      {adding && (
        <form onSubmit={handleSubmit} className="mt-6 border border-line bg-surface p-6">
          <div className="grid gap-6 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Field id="h-headline" label="Headline" required value={values.headline} onChange={set('headline')} placeholder="Imported, cleared, delivered." />
            </div>
            <div className="sm:col-span-2">
              <Field id="h-subline" label="Subline" value={values.subline} onChange={set('subline')} />
            </div>
            <Field id="h-cta-label" label="Button text" value={values.cta_label} onChange={set('cta_label')} placeholder="Browse the stock" />
            <Field id="h-cta-url" label="Button link" value={values.cta_url} onChange={set('cta_url')} placeholder="/?body_type=suv" />

            <div>
              <label htmlFor="h-image" className={labelClass}>Poster image</label>
              <input
                id="h-image"
                type="file"
                accept="image/*"
                required
                onChange={(event) =>
                  setValues((c) => ({ ...c, image: event.target.files[0] ?? null }))
                }
                className="mt-2 w-full border border-line bg-surface p-3 text-meta"
              />
              <p className="mt-2 text-meta text-ink-mute">
                Always required - it is what renders on first paint and on mobile.
              </p>
            </div>

            <div>
              <label htmlFor="h-video" className={labelClass}>Video (optional)</label>
              <input
                id="h-video"
                type="file"
                accept="video/mp4,video/webm"
                onChange={(event) =>
                  setValues((c) => ({ ...c, video: event.target.files[0] ?? null }))
                }
                className="mt-2 w-full border border-line bg-surface p-3 text-meta"
              />
              <p className="mt-2 text-meta text-ink-mute">
                Under 5MB, desktop only, and strip the audio track first.
              </p>
            </div>
          </div>

          {create.isError && (
            <ul className="mt-6">
              {errorMessages(create.error).map((message) => (
                <li key={message} className="text-meta text-ink">{message}</li>
              ))}
            </ul>
          )}

          <Button
            size="large"
            className="mt-6"
            type="submit"
            disabled={create.isPending}
          >
            {create.isPending ? 'Uploading...' : 'Put it up'}
          </Button>
        </form>
      )}

      <div className="mt-6">
        {query.isPending ? (
          <div className="h-32 w-full animate-pulse bg-line" />
        ) : query.isError ? (
          <ErrorState message="We could not load the heroes." onRetry={query.refetch} />
        ) : banners.length === 0 ? (
          <p className="border border-line bg-surface p-6 text-meta text-ink-soft">
            No hero set. The shopfront falls back to its plain header.
          </p>
        ) : (
          <ul className="space-y-4">
            {banners.map((banner) => (
              <li
                key={banner.id}
                className="flex flex-wrap items-center gap-6 border border-line bg-surface p-4"
              >
                <img
                  src={banner.image}
                  alt=""
                  className="aspect-[16/9] w-40 shrink-0 border border-line object-cover"
                />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-3">
                    <p className="text-model">{banner.headline}</p>
                    {banner.is_live && (
                      <span className="rounded-full bg-ink px-3 py-1 text-badge uppercase text-surface">
                        On the site
                      </span>
                    )}
                    {banner.is_active && !banner.is_live && (
                      <span className="rounded-full border border-line px-3 py-1 text-badge uppercase text-ink-soft">
                        Active, superseded
                      </span>
                    )}
                  </div>
                  {banner.subline && (
                    <p className="mt-1 text-meta text-ink-soft">{banner.subline}</p>
                  )}
                  <p className="mt-1 text-meta text-ink-mute">
                    {banner.video ? 'With video · ' : ''}
                    updated {new Date(banner.updated_at).toLocaleDateString('en-KE')}
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-4">
                  <button
                    type="button"
                    disabled={update.isPending}
                    onClick={() =>
                      update.mutate({ id: banner.id, is_active: !banner.is_active })
                    }
                    className="text-meta text-ink underline disabled:opacity-50"
                  >
                    {banner.is_active ? 'Take down' : 'Put up'}
                  </button>
                  {/* Only a Manager may delete - the API refuses Sales, so
                      offering the control would be a promise it breaks. */}
                  {isManager && (
                    <button
                      type="button"
                      disabled={remove.isPending}
                      onClick={() => remove.mutate(banner.id)}
                      className="text-meta text-ink-soft underline disabled:opacity-50"
                    >
                      Delete
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
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
      <HeroSection />
      <RatesSection />
      {/* Staff accounts are a manager's business only - the API refuses Sales
          outright, so the section is not rendered rather than rendered and
          then refused. */}
      {isManager && <TeamSection />}
    </div>
  )
}

export default StaffSettings
