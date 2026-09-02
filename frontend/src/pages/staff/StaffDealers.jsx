import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import ApplicationCar from '../../components/ApplicationCar'
import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import { counted, formatPrice } from '../../lib/format'
import { useAuth } from '../../context/AuthContext'
import {
  useStaffDealerApplications,
  useStaffDealerListings,
  useStaffDealers,
} from '../../hooks/useStaffDealers'
import Button from '../../components/Button'

/** Reviewing dealerships and the cars they send us.
 *
 *  Sales can read all of it; only a Manager decides - taking on a dealership
 *  and putting somebody else's car on the site are both commitments. The
 *  buttons are hidden accordingly, and the API refuses regardless.
 *
 *  Applications also arrive in the Queue as tickets, which is where an agent
 *  claims one. This screen is the other half: the submissions, which have no
 *  ticket of their own because they arrive in bulk from dealers we have
 *  already said yes to.
 */

const TABS = [
  ['submissions', 'Car submissions'],
  ['applications', 'Applications'],
  ['dealerships', 'Dealerships'],
]

function Note({ value, onChange, placeholder }) {
  return (
    <input
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
      className="h-11 w-full max-w-[320px] border border-line bg-surface px-3 text-meta outline-none focus:border-ink"
    />
  )
}

function Decide({ id, decide, canDecide, approveLabel, placeholder }) {
  const [note, setNote] = useState('')

  if (!canDecide) {
    return (
      <p className="text-meta text-ink-mute">A manager decides this one.</p>
    )
  }

  const failed = decide.isError && decide.variables?.id === id

  return (
    <div className="flex flex-wrap items-center gap-4">
      <Note value={note} onChange={setNote} placeholder={placeholder} />
      <Button
        disabled={decide.isPending}
        onClick={() => decide.mutate({ id, action: 'approve', note })}
      >
        {approveLabel}
      </Button>
      <Button
        variant="secondary"
        disabled={decide.isPending}
        onClick={() => decide.mutate({ id, action: 'reject', note })}
      >
        Reject
      </Button>
      {failed && (
        <p className="w-full text-meta text-ink">
          {decide.error?.response?.data?.error ?? 'That did not go through.'}
        </p>
      )}
    </div>
  )
}

function Submissions({ canDecide }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const status = searchParams.get('status') ?? 'submitted'
  const { query, decide } = useStaffDealerListings({ status })

  const rows = query.data?.results ?? []

  function setStatus(value) {
    const next = new URLSearchParams(searchParams)
    next.set('status', value)
    setSearchParams(next)
  }

  return (
    <div>
      <nav className="flex flex-wrap gap-6">
        {[
          ['submitted', 'Waiting'],
          ['approved', 'Listed'],
          ['rejected', 'Rejected'],
          ['withdrawn', 'Withdrawn'],
        ].map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setStatus(value)}
            className={`text-meta transition-colors ${
              status === value
                ? 'text-ink underline underline-offset-4'
                : 'text-ink-soft hover:text-ink'
            }`}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="mt-8">
        {query.isLoading && <div className="h-64 w-full animate-pulse bg-line" />}
        {query.isError && <ErrorState onRetry={query.refetch} />}
        {query.isSuccess && rows.length === 0 && (
          <EmptyState
            title="Nothing waiting"
            message="No dealer submissions in this state."
          />
        )}

        {rows.length > 0 && (
          <ul className="space-y-4">
            {rows.map((listing) => (
              <li key={listing.id} className="border border-line bg-surface p-6">
                <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
                  <div className="flex gap-6">
                    {listing.images[0] ? (
                      <img
                        src={listing.images[0].image}
                        alt=""
                        loading="eager"
                        className="h-24 w-32 shrink-0 border border-line object-cover"
                      />
                    ) : (
                      <div className="flex h-24 w-32 shrink-0 items-center justify-center border border-line">
                        <span className="text-badge uppercase text-ink-mute">
                          No photo
                        </span>
                      </div>
                    )}

                    <div>
                      <p className="text-model">
                        {listing.year} {listing.make} {listing.model}
                      </p>
                      <p className="mt-1 text-meta text-ink-soft">
                        {listing.dealer_name} · {formatPrice(listing.price)} ·{' '}
                        {counted(listing.images.length, 'photo')}
                      </p>
                      {listing.description && (
                        <p className="mt-3 max-w-[560px] text-meta text-ink-soft">
                          {listing.description}
                        </p>
                      )}
                      {listing.published_car_id && (
                        <Link
                          to={`/cars/${listing.published_car_id}`}
                          className="mt-3 inline-block text-meta text-ink underline underline-offset-4"
                        >
                          See the listing
                        </Link>
                      )}
                    </div>
                  </div>
                </div>

                {listing.status === 'submitted' && (
                  <div className="mt-6 border-t border-line pt-6">
                    <Decide
                      id={listing.id}
                      decide={decide}
                      canDecide={canDecide}
                      approveLabel="Publish"
                      placeholder="Why, if you are rejecting it"
                    />
                    {listing.images.length === 0 && (
                      <p className="mt-4 text-meta text-ink-mute">
                        No photographs. Publishing puts it on the site without
                        one.
                      </p>
                    )}
                  </div>
                )}

                {listing.decision_note && listing.status !== 'submitted' && (
                  <p className="mt-6 border-t border-line pt-6 text-meta text-ink-soft">
                    {listing.decision_note}
                    {listing.reviewed_by_name && ` — ${listing.reviewed_by_name}`}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

function Applications({ canDecide }) {
  const [status, setStatus] = useState('pending')
  const { query, decide } = useStaffDealerApplications({ status })
  const rows = query.data?.results ?? []

  return (
    <div>
      <nav className="flex flex-wrap gap-6">
        {[
          ['pending', 'Waiting'],
          ['approved', 'Approved'],
          ['rejected', 'Rejected'],
        ].map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setStatus(value)}
            className={`text-meta transition-colors ${
              status === value
                ? 'text-ink underline underline-offset-4'
                : 'text-ink-soft hover:text-ink'
            }`}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="mt-8">
        {query.isLoading && <div className="h-64 w-full animate-pulse bg-line" />}
        {query.isError && <ErrorState onRetry={query.refetch} />}
        {query.isSuccess && rows.length === 0 && (
          <EmptyState
            title="No applications"
            message="Nobody is waiting on an answer."
          />
        )}

        {rows.length > 0 && (
          <ul className="space-y-4">
            {rows.map((application) => (
              <li
                key={application.id}
                className="border border-line bg-surface p-6"
              >
                <div className="flex flex-wrap items-center gap-3">
                  <p className="text-model">{application.display_name}</p>
                  <span className="rounded-full border border-line px-3 py-1 text-badge uppercase text-ink-soft">
                    {application.seller_type_label}
                  </span>
                </div>
                <p className="mt-1 text-meta text-ink-soft">
                  {application.contact_name} · {application.phone} ·{' '}
                  {application.email}
                </p>
                <dl className="mt-4 flex flex-wrap gap-x-10 gap-y-3 text-meta">
                  <div>
                    <dt className="text-ink-soft">Where</dt>
                    <dd className="mt-1">{application.location}</dd>
                  </div>
                  {application.seller_type === 'dealer' ? (
                    <div>
                      <dt className="text-ink-soft">Cars to sell</dt>
                      <dd className="mt-1">
                        {application.fleet_size ?? 'Not stated'}
                      </dd>
                    </div>
                  ) : (
                    <div>
                      <dt className="text-ink-soft">ID or passport</dt>
                      <dd className="mt-1">
                        {application.id_number || 'Not given'}
                      </dd>
                    </div>
                  )}
                </dl>

                {application.message && (
                  <p className="mt-4 max-w-[560px] text-meta text-ink-soft">
                    {application.message}
                  </p>
                )}

                <div className="mt-6 border-t border-line pt-6">
                  <ApplicationCar
                    cars={application.cars ?? []}
                    documents={application.documents ?? []}
                  />
                </div>

                {application.status === 'pending' ? (
                  <div className="mt-6 border-t border-line pt-6">
                    <Decide
                      id={application.id}
                      decide={decide}
                      canDecide={canDecide}
                      approveLabel="Take them on and list"
                      placeholder="A note they will read"
                    />
                    <p className="mt-4 text-meta text-ink-mute">
                      Approving creates their account, emails them a link to set
                      a password - we never send one - and puts the car above on
                      the site immediately.
                    </p>
                  </div>
                ) : (
                  <p className="mt-6 border-t border-line pt-6 text-meta text-ink-soft">
                    {application.status_label ?? application.status}
                    {application.reviewed_by_name &&
                      ` by ${application.reviewed_by_name}`}
                    {application.decision_note && ` — ${application.decision_note}`}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

function Dealerships({ canDecide }) {
  const { query, update } = useStaffDealers()
  const rows = query.data?.results ?? []

  if (query.isLoading) return <div className="h-64 w-full animate-pulse bg-line" />
  if (query.isError) return <ErrorState onRetry={query.refetch} />
  if (rows.length === 0) {
    return (
      <EmptyState
        title="Nobody approved yet"
        message="Approved applications appear here."
      />
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-meta">
        <thead>
          <tr className="border-b border-line text-left text-badge uppercase text-ink-soft">
            <th scope="col" className="py-3 pr-6 font-normal">Seller</th>
            <th scope="col" className="py-3 pr-6 font-normal">Contact</th>
            <th scope="col" className="py-3 pr-6 font-normal">Live</th>
            <th scope="col" className="py-3 pr-6 font-normal">Waiting</th>
            <th scope="col" className="py-3 font-normal">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((dealer) => (
            <tr key={dealer.id} className="border-b border-line">
              <th scope="row" className="py-4 pr-6 text-left font-normal">
                <span className={dealer.is_active ? '' : 'text-ink-mute'}>
                  {dealer.name}
                </span>
                <span className="mt-1 block text-ink-mute">
                  {dealer.seller_type_label} · {dealer.location}
                </span>
              </th>
              <td className="py-4 pr-6 text-ink-soft">
                {dealer.contact_name}
                <span className="mt-1 block">{dealer.phone}</span>
              </td>
              <td className="py-4 pr-6">{dealer.listings_live}</td>
              <td className="py-4 pr-6 text-ink-soft">{dealer.listings_waiting}</td>
              <td className="py-4">
                {canDecide ? (
                  <button
                    type="button"
                    onClick={() =>
                      update.mutate({ id: dealer.id, is_active: !dealer.is_active })
                    }
                    className="text-ink underline underline-offset-4"
                  >
                    {dealer.is_active ? 'Suspend' : 'Reinstate'}
                  </button>
                ) : (
                  <span className="text-ink-soft">
                    {dealer.is_active ? 'Active' : 'Suspended'}
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function StaffDealers() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') ?? 'submissions'
  const { isManager } = useAuth()

  function setTab(value) {
    const next = new URLSearchParams(searchParams)
    next.set('tab', value)
    // The two lists filter on different values of the same param, so carrying
    // one across would land the other on a state it has never heard of.
    next.delete('status')
    setSearchParams(next)
  }

  return (
    <div>
      <h2 className="font-serif text-h1">Dealers</h2>
      <p className="mt-2 text-meta text-ink-soft">
        Dealerships and private owners selling through us, and the cars they
        send. Nothing here is on the site until it is published.
      </p>

      <nav className="mt-8 flex flex-wrap gap-6 border-b border-line">
        {TABS.map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setTab(value)}
            className={`-mb-px border-b-2 pb-3 text-meta transition-colors ${
              tab === value
                ? 'border-ink text-ink'
                : 'border-transparent text-ink-soft hover:text-ink'
            }`}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="mt-10">
        {tab === 'submissions' && <Submissions canDecide={isManager} />}
        {tab === 'applications' && <Applications canDecide={isManager} />}
        {tab === 'dealerships' && <Dealerships canDecide={isManager} />}
      </div>
    </div>
  )
}

export default StaffDealers
