import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import ConfirmChoice from '../components/ConfirmChoice'
import ErrorState from '../components/ErrorState'
import Page from '../components/Page'
import SourcedUnitCard from '../components/SourcedUnitCard'
import { errorMessages } from '../lib/errors'
import { useImportRequest } from '../hooks/useImportRequest'

const STAGES = [
  ['pending', 'Received'],
  ['sourcing', 'Sourcing'],
  ['awaiting_selection', 'Your choice'],
  ['agreed', 'Agreed'],
]

/** What is happening, in a sentence, for each state the request can be in.
 *  A progress rail alone leaves people guessing whether it is their move. */
const EXPLANATION = {
  pending: 'We have your request and are about to start looking.',
  sourcing:
    'Our team is searching auctions in Japan. We will email you the moment we have units to show you.',
  awaiting_selection:
    'Here is what we found. Take your time — choosing one declines the rest.',
  agreed:
    'You have chosen your unit. We will be in touch to confirm the agreement and arrange payment.',
  cancelled: 'This request was cancelled.',
}

function ImportTracking() {
  const { token } = useParams()
  const { query, decide } = useImportRequest(token)
  const [confirming, setConfirming] = useState(null)

  if (query.isPending) {
    return (
      <Page>
        <div className="h-8 w-64 animate-pulse bg-line" />
        <div className="mt-8 h-40 w-full max-w-[640px] animate-pulse bg-line" />
      </Page>
    )
  }

  if (query.isError) {
    const missing = query.error?.response?.status === 404
    return (
      <Page>
        <ErrorState
          title={missing ? 'Request not found' : 'Something went wrong'}
          message={
            missing
              ? 'Check the link in your email — it may have been copied incompletely.'
              : 'We could not load this request.'
          }
          onRetry={missing ? undefined : query.refetch}
        />
      </Page>
    )
  }

  const request = query.data
  const units = request.units ?? []
  const chosen = units.find((unit) => unit.status === 'selected')
  const reached = STAGES.findIndex(([key]) => key === request.status)
  const cancelled = request.status === 'cancelled'

  function handleDecide(unit, decision) {
    // Choosing declines everything else, which is not obvious from a button
    // labelled "choose this one" and cannot be undone here.
    if (decision === 'select' && units.length > 1) {
      setConfirming(unit)
      return
    }
    decide.mutate({ unitId: unit.id, decision })
  }

  return (
    <Page>
      <p className="text-badge uppercase text-ink-soft">Import request</p>
      <h1 className="mt-3 font-serif text-h1">
        {request.year} {request.make} {request.model}
      </h1>

      <div className="mt-10 border border-line bg-surface p-6 lg:p-8">
        <ol className="flex flex-wrap gap-x-2 gap-y-3">
          {STAGES.map(([key, label], index) => {
            const done = !cancelled && index <= reached
            return (
              <li key={key} className="flex items-center gap-2">
                <span
                  aria-hidden="true"
                  className={`h-2 w-2 rounded-full ${done ? 'bg-ink' : 'bg-line'}`}
                />
                <span
                  className={`text-badge uppercase ${done ? 'text-ink' : 'text-ink-mute'}`}
                >
                  {label}
                </span>
                {index < STAGES.length - 1 && (
                  <span aria-hidden="true" className="ml-1 h-px w-6 bg-line" />
                )}
              </li>
            )
          })}
        </ol>

        <p className="mt-6 max-w-[68ch] text-model leading-relaxed text-ink-soft">
          {EXPLANATION[request.status]}
        </p>
      </div>

      {decide.isError && (
        <ul className="mt-8">
          {errorMessages(decide.error).map((message) => (
            <li key={message} className="text-meta text-ink">
              {message}
            </li>
          ))}
        </ul>
      )}

      {units.length > 0 && (
        <section className="mt-16">
          <h2 className="font-serif text-section">
            {chosen ? 'Your unit' : `${units.length} found so far`}
          </h2>
          <div className="mt-6 space-y-6">
            {units.map((unit) => (
              <SourcedUnitCard
                key={unit.id}
                unit={unit}
                onDecide={handleDecide}
                isDeciding={decide.isPending}
                decided={Boolean(chosen)}
              />
            ))}
          </div>
        </section>
      )}

      <p className="mt-16 max-w-[68ch] text-meta text-ink-mute">
        Keep this link — it is the only way back to this request, and anyone
        holding it can see what is on this page.
      </p>

      <Link to="/" className="mt-8 inline-block text-meta text-ink underline">
        Browse cars in stock
      </Link>

      {confirming && (
        <ConfirmChoice
          unit={confirming}
          others={units.length - 1}
          isPending={decide.isPending}
          onCancel={() => setConfirming(null)}
          onConfirm={() => {
            decide.mutate(
              { unitId: confirming.id, decision: 'select' },
              { onSettled: () => setConfirming(null) },
            )
          }}
        />
      )}
    </Page>
  )
}

export default ImportTracking
