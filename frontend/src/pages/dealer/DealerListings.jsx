import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import ConfirmModal from '../../components/ConfirmModal'
import DealerListingModal from '../../components/DealerListingModal'
import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import { counted, formatPrice } from '../../lib/format'
import { LISTING_STATES, useDealerListings, useDealerProfile } from '../../hooks/useDealer'
import Button from '../../components/Button'

/** A dealership's own stock, and where each car has got to.
 *
 *  The states are named for what the dealer is waiting on rather than for what
 *  the column stores - "Waiting on us" is a promise, "Submitted" is a database
 *  value. The filter is in the URL like every other list on this site, so a
 *  view can be sent to a colleague.
 */

const VIEWS = [['', 'All'], ...LISTING_STATES]

const LABELS = Object.fromEntries(LISTING_STATES)

function Badge({ status }) {
  // Our own wording, not the API's display value: the tabs promise "waiting on
  // us" and a badge reading "Submitted" three centimetres away is the same
  // state described two ways.
  const label = LABELS[status] ?? status
  const live = status === 'approved'
  return (
    <span
      className={`rounded-full px-3 py-1 text-badge uppercase ${
        live
          ? 'bg-ink text-surface'
          : 'border border-line text-ink-soft'
      }`}
    >
      {label}
    </span>
  )
}

function DealerListings() {
  const [searchParams, setSearchParams] = useSearchParams()
  const status = searchParams.get('status') ?? ''

  const [editing, setEditing] = useState(null)
  const [adding, setAdding] = useState(false)
  const [withdrawing, setWithdrawing] = useState(null)

  const { data: dealer } = useDealerProfile()
  const { query, create, update, withdraw, addPhoto, removePhoto } =
    useDealerListings({ status })

  function setView(value) {
    const next = new URLSearchParams(searchParams)
    if (value) next.set('status', value)
    else next.delete('status')
    setSearchParams(next)
  }

  const rows = query.data?.results ?? []

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-4">
        <div>
          <h1 className="font-serif text-h1">Your cars</h1>
          <p className="mt-2 text-meta text-ink-soft">
            {dealer
              ? `${counted(dealer.listings_live, 'car')} live · ${counted(
                  dealer.listings_waiting,
                  'car',
                )} waiting on us`
              : ' '}
          </p>
        </div>

        <Button
          size="large"
          onClick={() => setAdding(true)}
        >
          Submit a car
        </Button>
      </div>

      <nav className="mt-8 flex flex-wrap gap-6 border-b border-line">
        {VIEWS.map(([value, label]) => (
          <button
            key={value || 'all'}
            type="button"
            onClick={() => setView(value)}
            className={`-mb-px border-b-2 pb-3 text-meta transition-colors ${
              status === value
                ? 'border-ink text-ink'
                : 'border-transparent text-ink-soft hover:text-ink'
            }`}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="mt-10">
        {query.isLoading && <div className="h-64 w-full animate-pulse bg-line" />}

        {query.isError && (
          <ErrorState
            title="Your cars could not be loaded"
            onRetry={query.refetch}
          />
        )}

        {query.isSuccess && rows.length === 0 && (
          <EmptyState
            title="Nothing here yet"
            message={
              status
                ? 'No cars of yours are in this state.'
                : 'Submit your first car and our team will check it over.'
            }
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
                        className="h-20 w-28 shrink-0 border border-line object-cover"
                      />
                    ) : (
                      <div className="flex h-20 w-28 shrink-0 items-center justify-center border border-line">
                        <span className="text-badge uppercase text-ink-mute">
                          No photo
                        </span>
                      </div>
                    )}

                    <div>
                      <div className="flex flex-wrap items-center gap-3">
                        <p className="text-model">
                          {listing.year} {listing.make} {listing.model}
                        </p>
                        <Badge status={listing.status} />
                      </div>
                      <p className="mt-1 text-meta text-ink-soft">
                        {formatPrice(listing.price)}
                        {listing.mileage_km
                          ? ` · ${listing.mileage_km.toLocaleString('en-KE')} km`
                          : ''}
                        {` · ${counted(listing.images.length, 'photo')}`}
                      </p>
                      {listing.decision_note && (
                        <p className="mt-3 max-w-[520px] text-meta text-ink-soft">
                          {listing.decision_note}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-4">
                    {listing.is_editable && (
                      <Button
                        variant="secondary"
                        onClick={() => setEditing(listing)}
                      >
                        {listing.status === 'rejected' ? 'Fix and resend' : 'Edit'}
                      </Button>
                    )}
                    {listing.status === 'submitted' && (
                      <Button
                        variant="quiet"
                        onClick={() => setWithdrawing(listing)}
                      >
                        Withdraw
                      </Button>
                    )}
                    {listing.status === 'approved' && listing.published_car_id && (
                      <Link
                        to={`/cars/${listing.published_car_id}`}
                        className="text-meta text-ink underline underline-offset-4"
                      >
                        See it on the site
                      </Link>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {(adding || editing) && (
        <DealerListingModal
          listing={editing}
          create={create}
          update={update}
          photos={{ addPhoto, removePhoto }}
          onClose={() => {
            setAdding(false)
            setEditing(null)
          }}
        />
      )}

      {withdrawing && (
        <ConfirmModal
          title="Withdraw this car?"
          body={`${withdrawing.year} ${withdrawing.make} ${withdrawing.model} will leave our queue. You can submit it again later.`}
          confirmLabel="Withdraw"
          mutation={withdraw}
          onConfirm={() =>
            withdraw.mutate(withdrawing.id, {
              onSuccess: () => setWithdrawing(null),
            })
          }
          onClose={() => setWithdrawing(null)}
        />
      )}
    </div>
  )
}

export default DealerListings
