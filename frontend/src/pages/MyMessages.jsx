import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import ChatThread from '../components/ChatThread'
import EmptyState from '../components/EmptyState'
import ErrorState from '../components/ErrorState'
import { useMyChat, useMyThreads } from '../hooks/useChat'

function when(stamp) {
  if (!stamp) return ''
  const at = new Date(stamp)
  const today = new Date().toDateString() === at.toDateString()
  return today
    ? at.toLocaleTimeString('en-KE', { hour: '2-digit', minute: '2-digit' })
    : at.toLocaleDateString('en-KE')
}

/** The customer's threads, one per thing they have going.
 *
 *  A list rather than a single conversation: chat hangs off the work, so
 *  somebody with an enquiry and an import has two, and which one they mean
 *  matters to whoever answers.
 */
function MyMessages() {
  const [searchParams, setSearchParams] = useSearchParams()
  const openId = searchParams.get('about')

  const threads = useMyThreads()
  const { query, send, markRead } = useMyChat(openId)
  const unread = query.data?.unread ?? 0

  useEffect(() => {
    if (openId && unread > 0) markRead.mutate()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openId, unread])

  const rows = threads.data ?? []

  return (
    <div>
      <h1 className="font-serif text-section">Messages</h1>
      <p className="mt-1 text-meta text-ink-soft">
        One conversation for each thing you have with us.
      </p>

      {threads.isPending ? (
        <div className="mt-8 h-64 w-full animate-pulse bg-line" />
      ) : threads.isError ? (
        <div className="mt-8">
          <ErrorState
            message="We could not open your messages."
            onRetry={threads.refetch}
          />
        </div>
      ) : rows.length === 0 ? (
        <div className="mt-8">
          <EmptyState
            title="Nothing yet"
            message="Ask about a car, or request an import, and the conversation starts here."
          />
        </div>
      ) : (
        <div className="mt-8 grid gap-8 lg:grid-cols-[280px_1fr]">
          <ul className="space-y-2">
            {rows.map((row) => (
              <li key={row.id}>
                <button
                  type="button"
                  onClick={() => setSearchParams({ about: String(row.ticket_id) })}
                  className={`w-full border p-4 text-left transition-colors ${
                    String(row.ticket_id) === String(openId)
                      ? 'border-ink bg-surface'
                      : 'border-line hover:border-ink'
                  }`}
                >
                  <div className="flex items-baseline justify-between gap-3">
                    <p className="text-meta uppercase text-ink-soft">
                      {row.ticket_kind_label}
                    </p>
                    <span className="shrink-0 text-meta text-ink-mute">
                      {when(row.last_message_at)}
                    </span>
                  </div>
                  {row.last_message && (
                    <p className="mt-1 truncate text-meta">
                      {row.last_message.from_staff ? 'Goldride: ' : 'You: '}
                      {row.last_message.body}
                    </p>
                  )}
                  {row.unread > 0 && (
                    <span className="mt-2 inline-block rounded-full bg-ink px-3 py-1 text-badge uppercase text-surface">
                      {row.unread} new
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>

          <div className="h-[60vh] border border-line">
            {!openId ? (
              <div className="flex h-full items-center justify-center p-8">
                <EmptyState
                  title="Pick a conversation"
                  message="Choose one on the left to read and reply."
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
              <ChatThread
                messages={query.data.messages}
                send={send}
                mine={(message) => !message.from_staff}
                emptyMessage="Nothing said yet. Ask us anything."
                placeholder="Type your message..."
              />
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default MyMessages
