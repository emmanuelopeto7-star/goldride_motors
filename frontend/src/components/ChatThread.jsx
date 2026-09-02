import { useEffect, useRef, useState } from 'react'
import { errorMessages } from '../lib/errors'
import Button from './Button'

function when(stamp) {
  const at = new Date(stamp)
  const today = new Date().toDateString() === at.toDateString()
  return today
    ? at.toLocaleTimeString('en-KE', { hour: '2-digit', minute: '2-digit' })
    : at.toLocaleDateString('en-KE')
}

/** The transcript and the box to add to it, used by both sides.
 *
 *  Whose messages sit on the right differs: to a customer their own words are
 *  theirs, to staff the dealership's are. So the side is decided by `mine`
 *  rather than by who sent it, and one component serves both.
 */
function ChatThread({ messages, send, mine, emptyMessage, placeholder }) {
  const [body, setBody] = useState('')
  const bottom = useRef(null)

  // Follow the conversation down as it grows, the way every chat does.
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: 'nearest' })
  }, [messages.length])

  function handleSubmit(event) {
    event.preventDefault()
    const text = body.trim()
    if (!text) return
    // Cleared straight away: waiting for the round trip to empty the box
    // makes a fast connection feel slow and a slow one feel broken.
    setBody('')
    send.mutate(text, { onError: () => setBody(text) })
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto p-6">
        {messages.length === 0 ? (
          <p className="text-meta text-ink-soft">{emptyMessage}</p>
        ) : (
          messages.map((message) => {
            const isMine = mine(message)
            return (
              <div
                key={message.id}
                className={`flex ${isMine ? 'justify-end' : 'justify-start'}`}
              >
                <div className={`max-w-[80%] ${isMine ? 'text-right' : ''}`}>
                  <p className="text-badge uppercase text-ink-mute">
                    {isMine ? 'You' : message.sender_name} · {when(message.created_at)}
                  </p>
                  <p
                    className={`mt-2 inline-block whitespace-pre-line border p-4 text-left text-meta leading-relaxed ${
                      isMine
                        ? 'border-ink bg-ink text-surface'
                        : 'border-line bg-surface'
                    }`}
                  >
                    {message.body}
                  </p>
                </div>
              </div>
            )
          })
        )}
        <div ref={bottom} />
      </div>

      <form onSubmit={handleSubmit} className="border-t border-line p-4">
        {send.isError && (
          <ul className="mb-3">
            {errorMessages(send.error).map((message) => (
              <li key={message} className="text-meta text-ink">{message}</li>
            ))}
          </ul>
        )}

        <div className="flex items-end gap-3">
          <textarea
            rows={2}
            value={body}
            onChange={(event) => setBody(event.target.value)}
            onKeyDown={(event) => {
              // Enter sends, shift+enter breaks the line - what everyone
              // expects from a message box, and nothing else does here.
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                handleSubmit(event)
              }
            }}
            placeholder={placeholder}
            className="flex-1 resize-none border border-line bg-surface p-3 text-meta leading-relaxed outline-none focus:border-ink"
          />
          <Button
            size="large"
            type="submit"
            disabled={send.isPending || !body.trim()}
          >
            Send
          </Button>
        </div>
      </form>
    </div>
  )
}

export default ChatThread
