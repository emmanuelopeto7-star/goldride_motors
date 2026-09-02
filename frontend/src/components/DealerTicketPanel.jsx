import { useState } from 'react'
import { Link } from 'react-router-dom'
import ApplicationCar from './ApplicationCar'
import { useAuth } from '../context/AuthContext'
import { useStaffDealerApplications } from '../hooks/useStaffDealers'
import Button from './Button'

/** A dealer application, decided from inside its ticket.
 *
 *  The other panels on a ticket act on something we already hold - a car, an
 *  order. This one creates an account, so it says what approving actually
 *  does before anybody clicks: there is no undo, and the invitation goes out
 *  immediately.
 */
function DealerTicketPanel({ applicationId }) {
  const { isManager } = useAuth()
  const [note, setNote] = useState('')

  // The list is already fetched and cached for the Dealers screen; asking for
  // every pending application and picking one out avoids a second endpoint
  // that would return exactly the same row.
  const { query, decide } = useStaffDealerApplications({ status: '' })
  const application = (query.data?.results ?? []).find(
    (row) => row.id === applicationId,
  )

  if (query.isLoading) {
    return <div className="h-40 w-full animate-pulse bg-line" />
  }

  if (!application) {
    return (
      <p className="text-meta text-ink-soft">
        This application could not be loaded.
      </p>
    )
  }

  const decided = application.status !== 'pending'

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-3">
        <div>
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
        </div>
        <Link
          to="/staff/dealers?tab=applications"
          className="text-meta text-ink underline underline-offset-4"
        >
          All applications
        </Link>
      </div>

      <dl className="mt-6 flex flex-wrap gap-x-10 gap-y-3 text-meta">
        <div>
          <dt className="text-ink-soft">Where</dt>
          <dd className="mt-1">{application.location}</dd>
        </div>
        {/* A business is asked what it has to sell; a person is asked who
            they are. Showing the other one would be an empty row either way. */}
        {application.seller_type === 'dealer' ? (
          <div>
            <dt className="text-ink-soft">Cars to sell</dt>
            <dd className="mt-1">{application.fleet_size ?? 'Not stated'}</dd>
          </div>
        ) : (
          <div>
            <dt className="text-ink-soft">ID or passport</dt>
            <dd className="mt-1">{application.id_number || 'Not given'}</dd>
          </div>
        )}
      </dl>

      {application.message && (
        <p className="mt-6 max-w-[560px] text-meta text-ink-soft">
          {application.message}
        </p>
      )}

      <div className="mt-8 border-t border-line pt-6">
        <ApplicationCar
          cars={application.cars ?? []}
          documents={application.documents ?? []}
        />
      </div>

      {decided ? (
        <p className="mt-6 border-t border-line pt-6 text-meta text-ink-soft">
          {application.status === 'approved' ? 'Taken on' : 'Rejected'}
          {application.reviewed_by_name && ` by ${application.reviewed_by_name}`}
          {application.decision_note && ` — ${application.decision_note}`}
        </p>
      ) : (
        <div className="mt-6 border-t border-line pt-6">
          {isManager ? (
            <>
              <input
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder="A note they will read"
                className="h-11 w-full max-w-[420px] border border-line bg-surface px-3 text-meta outline-none focus:border-ink"
              />
              <div className="mt-4 flex flex-wrap items-center gap-4">
                <Button
                  disabled={decide.isPending}
                  onClick={() =>
                    decide.mutate({ id: application.id, action: 'approve', note })
                  }
                >
                  Take them on and list the car
                </Button>
                <Button
                  variant="secondary"
                  disabled={decide.isPending}
                  onClick={() =>
                    decide.mutate({ id: application.id, action: 'reject', note })
                  }
                >
                  Reject
                </Button>
              </div>
              <p className="mt-4 text-meta text-ink-mute">
                Approving does three things at once: creates their account,
                emails a link to set a password, and{' '}
                <span className="text-ink">
                  puts the car above on the site immediately
                </span>
                . There is no undo.
              </p>
              {decide.isError && (
                <p className="mt-4 text-meta text-ink">
                  {decide.error?.response?.data?.error ??
                    'That did not go through.'}
                </p>
              )}
            </>
          ) : (
            <p className="text-meta text-ink-mute">
              A manager decides whether we take this on.
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export default DealerTicketPanel
