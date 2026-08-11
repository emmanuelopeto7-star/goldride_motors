import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import { errorMessages } from '../lib/errors'
import { useAuth } from '../context/AuthContext'

const fieldClass =
  'h-12 w-full max-w-[420px] border border-line bg-surface px-4 text-model outline-none focus:border-ink'

function MyProfile() {
  const queryClient = useQueryClient()
  const { user, emailVerified, needsEmail, hasPassword, providers } = useAuth()

  const [firstName, setFirstName] = useState(user?.first_name ?? '')
  const [lastName, setLastName] = useState(user?.last_name ?? '')
  const [email, setEmail] = useState(user?.email ?? '')

  const save = useMutation({
    mutationFn: async () => {
      const res = await api.patch('/api/me/', {
        first_name: firstName,
        last_name: lastName,
        email,
      })
      return res.data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['me'] }),
  })

  const resend = useMutation({
    mutationFn: async () => {
      const res = await api.post('/api/auth/verify-email/resend/')
      return res.data
    },
  })

  function handleSubmit(event) {
    event.preventDefault()
    save.mutate()
  }

  return (
    <div className="max-w-[560px] space-y-12">
      <section>
        <h2 className="font-serif text-section">Your details</h2>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label htmlFor="first" className="text-meta text-ink-soft">
              First name
            </label>
            <input
              id="first"
              value={firstName}
              onChange={(event) => setFirstName(event.target.value)}
              className={`mt-2 ${fieldClass}`}
            />
          </div>

          <div>
            <label htmlFor="last" className="text-meta text-ink-soft">
              Last name
            </label>
            <input
              id="last"
              value={lastName}
              onChange={(event) => setLastName(event.target.value)}
              className={`mt-2 ${fieldClass}`}
            />
          </div>

          <div>
            <label htmlFor="email" className="text-meta text-ink-soft">
              Email address
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={`mt-2 ${fieldClass}`}
              required
            />
            {/* Changing it clears verification server-side, so say so first. */}
            <p className="mt-2 text-meta text-ink-mute">
              Changing this means confirming the new address again.
            </p>
          </div>

          {save.isError && (
            <ul className="space-y-1">
              {errorMessages(save.error).map((line) => (
                <li key={line} className="text-meta">
                  {line}
                </li>
              ))}
            </ul>
          )}

          {save.isSuccess && <p className="text-meta">Saved.</p>}

          <button
            type="submit"
            disabled={save.isPending}
            className="h-12 border border-ink px-8 text-badge uppercase disabled:opacity-50"
          >
            {save.isPending ? 'Saving…' : 'Save changes'}
          </button>
        </form>
      </section>

      <section className="border-t border-line pt-12">
        <h2 className="font-serif text-section">Email confirmation</h2>

        {needsEmail ? (
          <p className="mt-4 text-model text-ink-soft">
            Your account has no email address yet. Add one above so we can confirm
            orders and send receipts.
          </p>
        ) : emailVerified ? (
          <p className="mt-4 text-model text-ink-soft">
            {user.email} is confirmed.
          </p>
        ) : (
          <>
            <p className="mt-4 text-model text-ink-soft">
              {user.email} has not been confirmed yet. Open the link we emailed
              you, or send it again.
            </p>
            <button
              type="button"
              onClick={() => resend.mutate()}
              disabled={resend.isPending || resend.isSuccess}
              className="mt-4 h-12 border border-ink px-8 text-badge uppercase disabled:opacity-50"
            >
              {resend.isSuccess ? 'Sent' : resend.isPending ? 'Sending…' : 'Resend'}
            </button>
            {resend.isSuccess && (
              <p className="mt-3 text-meta text-ink-soft">
                {resend.data?.detail ?? 'Check your email for the link.'}
              </p>
            )}
          </>
        )}
      </section>

      <section className="border-t border-line pt-12">
        <h2 className="font-serif text-section">Sign-in methods</h2>
        <ul className="mt-4 space-y-2 text-model text-ink-soft">
          <li>Password: {hasPassword ? 'set' : 'not set'}</li>
          <li>
            Linked accounts:{' '}
            {providers.length > 0 ? providers.join(', ') : 'none'}
          </li>
        </ul>
      </section>
    </div>
  )
}

export default MyProfile
