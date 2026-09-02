import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import ChatThread from './ChatThread'
import { useAuth } from '../context/AuthContext'
import { useMyChat, useMyThreads } from '../hooks/useChat'

/** The chat button that follows you around the shopfront.
 *
 *  Chat hangs off tickets now, so there is no general thread to open: the
 *  button appears once you have something going - an enquiry, a purchase
 *  request, an import - and opens the most recent of them. That is nearly
 *  always the one you meant; the rest are a click away in the account.
 *
 *  Hidden on the Messages page, where the same conversations are already
 *  open full-size. Two composers for one thread is a bug the moment somebody
 *  types into the wrong one.
 */
function ChatLauncher() {
  const { isCustomer } = useAuth()
  const { pathname } = useLocation()

  if (!isCustomer || pathname.startsWith('/my/messages')) return null
  return <Threads />
}

/** Split out so the hooks below only run for a customer who can use them -
 *  opening a socket for every visitor to the home page would be a connection
 *  per stranger for nothing. */
function Threads() {
  const [open, setOpen] = useState(false)
  const threads = useMyThreads()
  const rows = threads.data ?? []

  // The most recently spoken in. The API already sorts that way, so this is
  // the conversation they are most likely to have come back for.
  const current = rows[0]
  const waiting = rows.reduce((total, row) => total + (row.unread ?? 0), 0)

  if (rows.length === 0) return null

  return (
    <Panel
      open={open}
      setOpen={setOpen}
      ticketId={current.ticket_id}
      label={current.ticket_kind_label}
      waiting={waiting}
      more={rows.length - 1}
    />
  )
}

function Panel({ open, setOpen, ticketId, label, waiting, more }) {
  const { query, send, markRead } = useMyChat(ticketId)
  const unread = query.data?.unread ?? 0

  useEffect(() => {
    if (open && unread > 0) markRead.mutate()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, unread])

  return (
    <>
      {open && (
        <div className="fixed bottom-24 right-6 z-50 flex h-[min(32rem,70vh)] w-[min(24rem,calc(100vw-3rem))] flex-col border border-ink bg-surface shadow-lg">
          <div className="flex items-start justify-between gap-3 border-b border-line p-4">
            <div className="min-w-0">
              <p className="text-model">Goldride</p>
              <p className="truncate text-meta text-ink-soft">
                About your {label.toLowerCase()}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close chat"
              className="shrink-0 text-meta text-ink-soft underline"
            >
              Close
            </button>
          </div>

          <div className="min-h-0 flex-1">
            {query.isPending ? (
              <div className="h-full w-full animate-pulse bg-line" />
            ) : (
              <ChatThread
                messages={query.data?.messages ?? []}
                send={send}
                mine={(message) => !message.from_staff}
                emptyMessage="Ask us anything about this."
                placeholder="Type your message..."
              />
            )}
          </div>

          {/* Only when there is somewhere else to go: a link to "all" when
              this is the only one would be a dead end. */}
          {more > 0 && (
            <div className="border-t border-line p-3 text-center">
              <Link
                to="/my/messages"
                className="text-meta text-ink underline"
                onClick={() => setOpen(false)}
              >
                {more === 1 ? 'One other conversation' : `${more} other conversations`}
              </Link>
            </div>
          )}
        </div>
      )}

      <button
        type="button"
        onClick={() => setOpen((was) => !was)}
        className="fixed bottom-6 right-6 z-50 flex h-14 items-center gap-3 border border-ink bg-ink px-6 text-badge uppercase text-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
      >
        {open ? 'Close' : 'Message us'}
        {/* Only when the panel is shut - a count beside an open conversation
            is telling you about what you are already reading. */}
        {!open && waiting > 0 && (
          <span className="flex h-6 min-w-6 items-center justify-center rounded-full bg-surface px-2 text-badge text-ink">
            {waiting}
          </span>
        )}
      </button>
    </>
  )
}

export default ChatLauncher
