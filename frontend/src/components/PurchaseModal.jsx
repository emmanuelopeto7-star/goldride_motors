import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import { formatPrice } from '../lib/format'
import { errorMessages } from '../lib/errors'
import { useAuth } from '../context/AuthContext'
import Modal from './Modal'
import Button from './Button'

const fieldClass =
  'h-12 w-full border border-line bg-surface px-4 text-model outline-none focus:border-ink'

function PurchaseModal({ car, title, onClose }) {
  const queryClient = useQueryClient()
  const { user, needsEmail } = useAuth()

  const [method, setMethod] = useState('mpesa')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState('')

  const request = useMutation({
    mutationFn: async () => {
      // Social sign-ins can arrive with no address, and an order has to be
      // confirmable somewhere. Add it first, then place the request.
      if (needsEmail) {
        await api.patch('/api/me/', { email })
      }

      const res = await api.post('/api/purchases/', {
        car: car.id,
        preferred_method: method,
        phone,
        message,
      })
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['me'] })
    },
  })

  function handleSubmit(event) {
    event.preventDefault()
    request.mutate()
  }

  return (
    <Modal onClose={onClose}>
      {request.isSuccess ? (
        <div className="text-center">
          <h2 className="font-serif text-section">Request sent</h2>
          <p className="mt-4 text-model text-ink-soft">
            Our sales team will review it and confirm. Once approved you will see
            the order and its payment here.
          </p>
          <Link
            to="/my/orders"
            className="mt-8 inline-block text-meta text-ink underline"
          >
            Go to my orders
          </Link>
        </div>
      ) : (
        <>
          <h2 className="text-center font-serif text-section">Request to buy</h2>
          <p className="mt-2 text-center text-meta text-ink-soft">
            {title} · {formatPrice(car.price)}
          </p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-4">
            {needsEmail && (
              <input
                type="email"
                aria-label="Email address"
                placeholder="Your email address"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className={fieldClass}
                required
              />
            )}

            <div className="flex gap-3">
              {[
                ['mpesa', 'M-PESA'],
                ['card', 'Card'],
              ].map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setMethod(key)}
                  aria-pressed={method === key}
                  className={`h-12 flex-1 border text-meta transition-colors ${
                    method === key
                      ? 'border-ink bg-ink text-surface'
                      : 'border-line hover:border-ink'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            <input
              type="tel"
              aria-label="Phone number"
              placeholder="Phone number, e.g. 254712345678"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              className={fieldClass}
              required
            />

            <textarea
              aria-label="Message"
              placeholder="Anything our team should know (optional)"
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              rows={3}
              className="w-full border border-line bg-surface p-4 text-model outline-none focus:border-ink"
            />

            {request.isError && (
              <ul className="space-y-1">
                {errorMessages(request.error).map((line) => (
                  <li key={line} className="text-meta">
                    {line}
                  </li>
                ))}
              </ul>
            )}

            <Button
              size="large"
              className="w-full"
              type="submit"
              disabled={request.isPending}
            >
              {request.isPending ? 'Sending…' : 'Send request'}
            </Button>

            <p className="text-meta text-ink-mute">
              This is a request, not a purchase. Nothing is charged until our team
              approves it and you complete payment as {user?.email || 'the account holder'}.
            </p>
          </form>
        </>
      )}
    </Modal>
  )
}

export default PurchaseModal
