import { Link, useSearchParams } from 'react-router-dom'
import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import Pagination from '../../components/Pagination'
import { formatPrice } from '../../lib/format'
import { useAuth } from '../../context/AuthContext'
import { useTicketActions, useTickets } from '../../hooks/useTickets'

const KINDS = [
  ['', 'Everything'],
  ['approval', 'Approvals'],
  ['sourcing', 'Sourcing'],
  ['enquiry', 'Enquiries'],
]

/** Who the queue is filtered to. "Unclaimed" is the one that matters on a busy
 *  morning: it is the work nobody has picked up yet. */
const OWNERS = [
  ['', 'All'],
  ['open', 'Unclaimed'],
  ['mine', 'Mine'],
]

function KindBadge({ ticket }) {
  // Monochrome, like every other badge on the dashboard: sourcing is outlined,
  // an approval - which holds money and a customer waiting - is filled.
  const filled = ticket.kind === 'approval'
  return (
    <span
      className={`shrink-0 rounded-full px-3 py-1 text-badge uppercase ${
        filled ? 'bg-ink text-surface' : 'border border-line text-ink-soft'
      }`}
    >
      {ticket.kind_label}
    </span>
  )
}

function StaffTickets() {
  const [searchParams, setSearchParams] = useSearchParams()
  const kind = searchParams.get('kind') ?? ''
  const owner = searchParams.get('owner') ?? ''
  const page = Math.max(1, Number(searchParams.get('page') ?? 1))
  const { user } = useAuth()

  const { data, isPending, isError, refetch } = useTickets({
    kind,
    status: owner === 'open' ? 'open' : '',
    mine: owner === 'mine',
    page,
  })
  const { claim } = useTicketActions()

  function setParam(next) {
    // Page is dropped on purpose: a different filter is a different result
    // set, and page 3 of it probably does not exist.
    const params = {}
    const nextKind = next.kind ?? kind
    const nextOwner = next.owner ?? owner
    if (nextKind) params.kind = nextKind
    if (nextOwner) params.owner = nextOwner
    setSearchParams(params)
  }

  const tickets = data?.results ?? []

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-6">
        <nav className="flex flex-wrap gap-6">
          {KINDS.map(([value, label]) => (
            <button
              key={label}
              type="button"
              onClick={() => setParam({ kind: value })}
              className={`text-meta transition-colors ${
                kind === value ? 'text-ink underline' : 'text-ink-soft hover:text-ink'
              }`}
            >
              {label}
            </button>
          ))}
        </nav>

        <nav className="flex flex-wrap gap-6">
          {OWNERS.map(([value, label]) => (
            <button
              key={label}
              type="button"
              onClick={() => setParam({ owner: value })}
              className={`text-meta transition-colors ${
                owner === value ? 'text-ink underline' : 'text-ink-soft hover:text-ink'
              }`}
            >
              {label}
            </button>
          ))}
        </nav>
      </div>

      <div className="mt-8">
        {isPending ? (
          <div className="h-64 w-full animate-pulse bg-line" />
        ) : isError ? (
          <ErrorState message="We could not load the queue." onRetry={refetch} />
        ) : tickets.length === 0 ? (
          <EmptyState
            title="Nothing waiting"
            message="Approvals and sourcing requests appear here as they arrive."
          />
        ) : (
          <ul className="space-y-4">
            {tickets.map((ticket) => {
              const isMine = ticket.claimed_by_username === user?.username
              return (
                <li key={ticket.id} className="border border-line bg-surface p-6">
                  <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-3">
                        <Link
                          to={`/staff/tickets/${ticket.id}`}
                          className="text-model underline"
                        >
                          {ticket.title}
                        </Link>
                        <KindBadge ticket={ticket} />
                      </div>
                      <p className="mt-1 text-price">
                        {ticket.amount
                          ? formatPrice(ticket.amount)
                          : 'No budget given'}
                      </p>
                    </div>

                    <dl className="flex flex-wrap gap-x-10 gap-y-3 text-meta">
                      <div>
                        <dt className="text-ink-soft">Customer</dt>
                        <dd className="mt-1">{ticket.customer}</dd>
                      </div>
                      <div>
                        <dt className="text-ink-soft">Raised</dt>
                        <dd className="mt-1">
                          {new Date(ticket.created_at).toLocaleDateString('en-KE')}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-ink-soft">With</dt>
                        <dd className="mt-1">
                          {ticket.claimed_by_username ?? 'Nobody yet'}
                        </dd>
                      </div>
                    </dl>
                  </div>

                  <div className="mt-6 flex flex-wrap items-center gap-4 border-t border-line pt-6">
                    {ticket.status === 'open' ? (
                      <button
                        type="button"
                        disabled={claim.isPending}
                        onClick={() => claim.mutate(ticket.id)}
                        className="h-11 bg-ink px-6 text-badge uppercase text-surface disabled:opacity-50"
                      >
                        Claim
                      </button>
                    ) : (
                      <p className="text-meta text-ink-soft">
                        {isMine ? 'Yours.' : `With ${ticket.claimed_by_username}.`}
                      </p>
                    )}
                    <Link
                      to={`/staff/tickets/${ticket.id}`}
                      className="text-meta text-ink underline"
                    >
                      Open
                    </Link>
                  </div>

                  {/* Losing the race is a normal outcome, not a failure: say who
                      has it, so nobody has to ask the room. Held to the row it
                      happened on, and only while that agent still has it - the
                      mutation result outlives the state it describes. */}
                  {claim.data?.won === false &&
                    claim.data.ticket.id === ticket.id &&
                    ticket.claimed_by_username ===
                      claim.data.ticket.claimed_by_username && (
                      <p className="mt-4 text-meta text-ink">
                        {claim.data.ticket.claimed_by_username} claimed this one
                        first.
                      </p>
                    )}
                </li>
              )
            })}
          </ul>
        )}
      </div>

      {data && (
        <Pagination
          count={data.count}
          hasNext={Boolean(data.next)}
          hasPrevious={Boolean(data.previous)}
        />
      )}
    </div>
  )
}

export default StaffTickets
