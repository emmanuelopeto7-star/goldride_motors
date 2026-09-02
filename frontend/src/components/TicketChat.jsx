import { useEffect } from 'react'
import ChatThread from './ChatThread'
import ErrorState from './ErrorState'
import { useStaffChat } from '../hooks/useChat'

/** The conversation about this ticket, on the ticket itself.
 *
 *  The reason chat moved off the customer and onto the work: an agent reading
 *  a sourcing request sees what was said about *that* request, in front of
 *  the quotes it is about, rather than in a separate inbox mixing it with an
 *  enquiry from March.
 */
function TicketChat({ ticketId, hasCustomer }) {
  const { query, send, markRead } = useStaffChat(hasCustomer ? ticketId : null)
  const unread = query.data?.unread ?? 0

  // Reading it here counts as reading it. Keyed on the count so a message
  // arriving while the ticket is open clears too.
  useEffect(() => {
    if (unread > 0) markRead.mutate()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [unread])

  if (!hasCustomer) {
    return (
      <p className="text-meta leading-relaxed text-ink-soft">
        This request came from a guest, so there is no account to message.
        Reach them on the phone or email number above.
      </p>
    )
  }

  if (query.isPending) {
    return <div className="h-64 w-full animate-pulse bg-line" />
  }

  if (query.isError) {
    return (
      <ErrorState
        message="We could not open this conversation."
        onRetry={query.refetch}
      />
    )
  }

  return (
    <div className="h-[28rem] border border-line">
      <ChatThread
        messages={query.data.messages}
        send={send}
        mine={(message) => message.from_staff}
        emptyMessage="Nothing said yet. Anything you send here reaches them in their account."
        placeholder="Reply to the customer..."
      />
    </div>
  )
}

export default TicketChat
