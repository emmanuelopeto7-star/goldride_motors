import { Link, useParams } from 'react-router-dom'
import ApprovalTicketPanel from '../../components/ApprovalTicketPanel'
import EnquiryTicketPanel from '../../components/EnquiryTicketPanel'
import ErrorState from '../../components/ErrorState'
import { useAuth } from '../../context/AuthContext'
import { useTicket, useTicketActions } from '../../hooks/useTickets'
import StaffSourcingDetail from './StaffSourcingDetail'

/** One ticket, whatever kind of work it turns out to be.
 *
 *  Everything above the rule is the same for every ticket: who owns it and how
 *  to take it, give it back or close it. Everything below dispatches on kind,
 *  because an approval and a sourcing request have nothing in common past the
 *  ownership - one is a decision on a price we already set, the other is a
 *  landed-cost calculation on a car we have not bought yet.
 */
function StaffTicketDetail() {
  const { id } = useParams()
  const { data: ticket, isPending, isError, refetch } = useTicket(id)
  const { claim, release, close, reply } = useTicketActions(id)
  const { user, isManager } = useAuth()

  if (isPending) return <div className="h-64 w-full animate-pulse bg-line" />

  if (isError) {
    return <ErrorState message="We could not load this ticket." onRetry={refetch} />
  }

  const isMine = ticket.claimed_by_username === user?.username
  const canHandOver = isMine || isManager
  const busy = claim.isPending || release.isPending || close.isPending

  return (
    <div>
      <Link to="/staff/tickets" className="text-meta text-ink underline">
        Back to the queue
      </Link>

      <header className="mt-6 border border-line bg-surface p-6">
        <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
          <div>
            <p className="text-badge uppercase text-ink-soft">
              {ticket.kind_label}
            </p>
            <h1 className="mt-1 font-serif text-section">{ticket.title}</h1>
            <p className="mt-1 text-meta text-ink-soft">
              For {ticket.customer} · raised{' '}
              {new Date(ticket.created_at).toLocaleDateString('en-KE')}
            </p>
          </div>

          <div className="text-meta">
            <p className="text-ink-soft">With</p>
            <p className="mt-1">
              {ticket.claimed_by_username
                ? isMine
                  ? 'You'
                  : ticket.claimed_by_username
                : 'Nobody yet'}
            </p>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-line pt-6">
          {ticket.status === 'open' && (
            <button
              type="button"
              disabled={busy}
              onClick={() => claim.mutate(ticket.id)}
              className="h-11 bg-ink px-6 text-badge uppercase text-surface disabled:opacity-50"
            >
              Claim it
            </button>
          )}

          {/* Handing a ticket back or closing it is the owner's to do, or a
              manager's. A peer cannot take work off a colleague - the API
              refuses it, so the buttons are not offered either. */}
          {ticket.status === 'claimed' && canHandOver && (
            <>
              <button
                type="button"
                disabled={busy}
                onClick={() => release.mutate(ticket.id)}
                className="h-11 border border-ink px-6 text-badge uppercase disabled:opacity-50"
              >
                {isMine ? 'Give it back' : 'Return to the queue'}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => close.mutate(ticket.id)}
                className="h-11 border border-ink px-6 text-badge uppercase disabled:opacity-50"
              >
                Close it
              </button>
            </>
          )}

          {ticket.status === 'claimed' && !canHandOver && (
            <p className="text-meta text-ink-soft">
              {ticket.claimed_by_username} is dealing with this one.
            </p>
          )}

          {ticket.status === 'closed' && (
            <p className="text-meta text-ink-soft">
              Closed
              {ticket.closed_at &&
                ` on ${new Date(ticket.closed_at).toLocaleDateString('en-KE')}`}
              {ticket.claimed_by_username && ` by ${ticket.claimed_by_username}`}.
            </p>
          )}

          {/* Only while the winner still holds it. A mutation result outlives
              the state it describes: release the ticket and this would go on
              saying somebody claimed it under a row that is now free. */}
          {claim.data?.won === false &&
            ticket.claimed_by_username &&
            ticket.claimed_by_username === claim.data.ticket.claimed_by_username && (
              <p className="text-meta text-ink">
                {claim.data.ticket.claimed_by_username} claimed this one first.
              </p>
            )}
        </div>
      </header>

      <section className="mt-8">
        {ticket.kind === 'approval' && (
          <div className="border border-line bg-surface p-6">
            <ApprovalTicketPanel requestId={ticket.subject_id} />
          </div>
        )}
        {ticket.kind === 'enquiry' && (
          <div className="border border-line bg-surface p-6">
            <EnquiryTicketPanel
              inquiryId={ticket.subject_id}
              ticketId={ticket.id}
              reply={reply}
            />
          </div>
        )}
        {ticket.kind === 'sourcing' && (
          <StaffSourcingDetail requestId={ticket.subject_id} />
        )}
      </section>
    </div>
  )
}

export default StaffTicketDetail
