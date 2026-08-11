import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import api from '../api/client'
import { errorMessages } from '../lib/errors'
import { useAuth } from '../context/AuthContext'
import AuthModal from './AuthModal'

const fieldClass =
  'h-12 w-full border border-line bg-surface px-4 text-model outline-none focus:border-ink'

function EnquiryPanel({ car, title }) {
  const { user } = useAuth()
  const [authOpen, setAuthOpen] = useState(false)
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [message, setMessage] = useState(`Please contact me regarding ${title}`)

  const enquiry = useMutation({
    mutationFn: async () => {
      const res = await api.post('/api/inquiries/', {
        car: car.id,
        name,
        phone,
        message,
      })
      return res.data
    },
  })

  function handleSubmit(event) {
    event.preventDefault()
    enquiry.mutate()
  }

  return (
    <aside className="h-fit border border-line bg-surface p-6 lg:sticky lg:top-32">
      <p className="font-serif text-section">Goldride Motors</p>
      <p className="mt-1 text-meta text-ink-soft">
        {car.location || 'Nairobi, Kenya'}
      </p>

      {enquiry.isSuccess ? (
        <p className="mt-6 border-t border-line pt-6 text-model">
          Thank you — your enquiry has been sent. Our sales team will be in touch.
        </p>
      ) : user ? (
        <form onSubmit={handleSubmit} className="mt-6 space-y-4 border-t border-line pt-6">
          <input
            aria-label="Your name"
            placeholder="Your name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            className={fieldClass}
          />

          <input
            type="tel"
            aria-label="Phone number"
            placeholder="Phone number"
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            className={fieldClass}
            required
          />

          <textarea
            aria-label="Your message"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            rows={4}
            className="w-full border border-line bg-surface p-4 text-model outline-none focus:border-ink"
          />

          {user.email && (
            <p className="text-meta text-ink-mute">We will reply to {user.email}</p>
          )}

          {enquiry.isError && (
            <ul className="space-y-1">
              {errorMessages(enquiry.error).map((line) => (
                <li key={line} className="text-meta">
                  {line}
                </li>
              ))}
            </ul>
          )}

          <button
            type="submit"
            disabled={enquiry.isPending}
            className="h-12 w-full bg-ink text-badge uppercase text-surface disabled:opacity-50"
          >
            {enquiry.isPending ? 'Sending…' : 'Send message'}
          </button>
        </form>
      ) : (
        <div className="mt-6 border-t border-line pt-6">
          <p className="text-model text-ink-soft">
            Sign in to send an enquiry about this car.
          </p>
          <button
            type="button"
            onClick={() => setAuthOpen(true)}
            className="mt-4 h-12 w-full bg-ink text-badge uppercase text-surface"
          >
            Sign in to enquire
          </button>
        </div>
      )}

      {authOpen && <AuthModal onClose={() => setAuthOpen(false)} />}
    </aside>
  )
}

export default EnquiryPanel
