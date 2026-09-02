import { useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import ChatThread from '../../components/ChatThread'
import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import { useChatInbox, useStaffChat } from '../../hooks/useChat'

function when(stamp) {
  if (!stamp) return ''
  const at = new Date(stamp)
  const today = new Date().toDateString() === at.toDateString()
  return today
    ? at.toLocaleTimeString('en-KE', { hour: '2-digit', minute: '2-digit' })
    : at.toLocaleDateString('en-KE')
}

/** The shared inbox.
 *
 *  Not filtered to one agent, unlike the ticket queue. Nobody owns a
 *  conversation: whoever is on shift answers, and a customer waiting must not
 *  be invisible because the colleague who last replied has gone home.
 */
function StaffChats() {
  const [searchParams, setSearchParams] = useSearchParams()
  const unreadOnly = searchParams.get('unread') === 'true'
  const openId = searchParams.get('about')

  const inbox = useChatInbox({ unreadOnly })
  const { query, send, markRead } = useStaffChat(openId)
  const unread = inbox.data?.results?.find(
    (row) => String(row.ticket_id) === String(openId),
  )?.unread

  useEffect(() => {
    if (openId && unread > 0) markRead.mutate()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openId, unread])

  function choose(id) {
    const params = {}
    if (unreadOnly) params.unread = 'true'
    if (id) params.about = String(id)
    setSearchParams(params)
  }

  const conversations = inbox.data?.results ?? []

  return (
    <div>
      <nav className="flex flex-wrap gap-6">
        {[['', 'All'], ['true', 'Waiting on us']].map(([value, label]) => (
          <button
            key={label}
            type="button"
            onClick={() => {
              const params = value ? { unread: 'true' } : {}
              if (openId) params.about = openId
              setSearchParams(params)
            }}
            className={`text-meta transition-colors ${
              (value === 'true') === unreadOnly
                ? 'text-ink underline'
                : 'text-ink-soft hover:text-ink'
            }`}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="mt-8 grid gap-8 lg:grid-cols-[320px_1fr]">
        <div>
          {inbox.isPending ? (
            <div className="h-64 w-full animate-pulse bg-line" />
          ) : inbox.isError ? (
            <ErrorState message="We could not load the inbox." onRetry={inbox.refetch} />
          ) : conversations.length === 0 ? (
            <p className="border border-line bg-surface p-6 text-meta text-ink-soft">
              {unreadOnly
                ? 'Nothing waiting on a reply.'
                : 'No conversations yet.'}
            </p>
          ) : (
            <ul className="space-y-2">
              {conversations.map((row) => (
                <li key={row.id}>
                  <button
                    type="button"
                    onClick={() => choose(row.ticket_id)}
                    className={`w-full border p-4 text-left transition-colors ${
                      String(row.ticket_id) === String(openId)
                        ? 'border-ink bg-surface'
                        : 'border-line hover:border-ink'
                    }`}
                  >
                    <div className="flex items-baseline justify-between gap-3">
                      <p className="text-model">{row.customer_name}</p>
                      <span className="shrink-0 text-meta text-ink-mute">
                        {when(row.last_message_at)}
                      </span>
                    </div>
                    {/* Which ticket, because "Wanjiru" is not enough to know
                        whether this is her sourcing request or an enquiry
                        from last month. */}
                    <p className="mt-1 text-meta uppercase text-ink-soft">
                      {row.ticket_kind_label}
                      {row.ticket_status === 'closed' && ' · settled'}
                    </p>
                    {row.last_message && (
                      <p className="mt-1 truncate text-meta text-ink-soft">
                        {row.last_message.from_staff ? 'You: ' : ''}
                        {row.last_message.body}
                      </p>
                    )}
                    {row.unread > 0 && (
                      <span className="mt-2 inline-block rounded-full bg-ink px-3 py-1 text-badge uppercase text-surface">
                        {row.unread} waiting
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="h-[70vh] border border-line">
          {!openId ? (
            <div className="flex h-full items-center justify-center p-8">
              <EmptyState
                title="Pick a conversation"
                message="Choose someone on the left to read and reply."
              />
            </div>
          ) : query.isPending ? (
            <div className="h-full w-full animate-pulse bg-line" />
          ) : query.isError ? (
            <div className="p-6">
              <ErrorState
                message="We could not open that conversation."
                onRetry={query.refetch}
              />
            </div>
          ) : (
            <div className="flex h-full flex-col">
              <div className="flex items-center justify-between gap-3 border-b border-line p-4">
                <p className="text-meta uppercase text-ink-soft">
                  {query.data.ticket_kind_label}
                </p>
                <Link
                  to={`/staff/tickets/${openId}`}
                  className="text-meta text-ink underline"
                >
                  Open the ticket
                </Link>
              </div>
              <div className="min-h-0 flex-1">
                <ChatThread
                  messages={query.data.messages}
                  send={send}
                  mine={(message) => message.from_staff}
                  emptyMessage="Nothing said yet."
                  placeholder="Reply..."
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default StaffChats
