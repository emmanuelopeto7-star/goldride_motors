import { useState } from 'react'
import ErrorState from './ErrorState'
import { useInquiry } from '../hooks/useInquiry'

/** The enquiry branch of a ticket: the question, and the one answer to it.
 *
 *  An answered enquiry shows the reply rather than an empty box, because the
 *  box is an invitation to send a second one. If two agents do reach send at
 *  the same moment the API refuses the loser outright - nothing is emailed -
 *  and this says who answered instead of pretending it went out.
 */
function EnquiryTicketPanel({ inquiryId, ticketId, reply }) {
  const { data: enquiry, isPending, isError, refetch } = useInquiry(inquiryId)
  const [message, setMessage] = useState('')

  if (isPending) return <div className="h-48 w-full animate-pulse bg-line" />

  if (isError) {
    return <ErrorState message="We could not load this enquiry." onRetry={refetch} />
  }

  const answered = Boolean(enquiry.replied_at)
  const refused = reply.data?.sent === false

  function handleSubmit(event) {
    event.preventDefault()
    const text = message.trim()
    if (text) reply.mutate({ ticketId, message: text })
  }

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
        <div className="min-w-0">
          <p className="text-model">{enquiry.car_display}</p>
        </div>

        <dl className="flex flex-wrap gap-x-12 gap-y-3 text-meta">
          <div>
            <dt className="text-ink-soft">Name</dt>
            <dd className="mt-1">{enquiry.name}</dd>
          </div>
          <div>
            <dt className="text-ink-soft">Phone</dt>
            <dd className="mt-1">{enquiry.phone}</dd>
          </div>
          <div>
            <dt className="text-ink-soft">Email</dt>
            <dd className="mt-1">{enquiry.email || 'Not given'}</dd>
          </div>
          <div>
            <dt className="text-ink-soft">Asked</dt>
            <dd className="mt-1">
              {new Date(enquiry.created_at).toLocaleDateString('en-KE')}
            </dd>
          </div>
        </dl>
      </div>

      {enquiry.message && (
        <p className="mt-6 max-w-[68ch] whitespace-pre-line border-t border-line pt-6 text-meta leading-relaxed text-ink-soft">
          {enquiry.message}
        </p>
      )}

      <div className="mt-8 border-t border-line pt-6">
        {answered ? (
          <div>
            <p className="text-badge uppercase text-ink-soft">
              Answered by {enquiry.replied_by_username ?? 'a colleague'} on{' '}
              {new Date(enquiry.replied_at).toLocaleDateString('en-KE')}
              {!enquiry.reply_emailed && ' · by phone'}
            </p>
            <p className="mt-3 max-w-[68ch] whitespace-pre-line text-meta leading-relaxed">
              {enquiry.reply}
            </p>
            {refused && (
              <p className="mt-4 text-meta text-ink">
                {reply.data.ticket.claimed_by_username
                  ? `${reply.data.ticket.claimed_by_username} answered this one first — nothing was sent.`
                  : 'Someone answered this one first — nothing was sent.'}
              </p>
            )}
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <label htmlFor="reply" className="text-badge uppercase text-ink-soft">
              Your reply
            </label>
            <textarea
              id="reply"
              rows={5}
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              placeholder="Yes, it is still available. Would you like to see it this week?"
              className="mt-3 w-full border border-line bg-surface p-4 text-meta leading-relaxed"
            />
            {/* Without this a failed send looks exactly like a click that
                never registered, and the agent tries again. */}
            {reply.isError && (
              <p className="mt-4 text-meta text-ink">
                That did not send. Nothing has reached the customer - try
                again.
              </p>
            )}

            <div className="mt-4 flex flex-wrap items-center gap-4">
              <button
                type="submit"
                disabled={reply.isPending || !message.trim()}
                className="h-12 bg-ink px-8 text-badge uppercase text-surface disabled:opacity-50"
              >
                {reply.isPending ? 'Sending...' : 'Send and close'}
              </button>
              {/* Said plainly, because it is the whole rule: one answer per
                  enquiry, and sending it takes the ticket out of the queue. */}
              <p className="text-meta text-ink-soft">
                {enquiry.email
                  ? 'Emails the customer and closes the ticket.'
                  : 'No email address — this records what you said on the phone.'}
              </p>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

export default EnquiryTicketPanel
