import { useState } from 'react'
import Button from '../components/Button'
import Page from '../components/Page'
import { errorMessages } from '../lib/errors'
import { useRequestPasswordReset } from '../hooks/usePassword'

/** Asking for a reset link.
 *
 *  The confirmation deliberately does not say whether an account was found.
 *  The API answers identically either way - telling somebody "no account with
 *  that address" turns this page into a free way to test whether a person
 *  banks here, and this site knows enough about its customers that membership
 *  alone is worth something.
 */

const fieldClass =
  'h-12 w-full border border-line bg-surface px-4 text-model outline-none focus:border-ink'

function ForgotPassword() {
  const [email, setEmail] = useState('')
  const request = useRequestPasswordReset()

  function handleSubmit(event) {
    event.preventDefault()
    request.mutate(email)
  }

  if (request.isSuccess) {
    return (
      <Page>
        <div className="mx-auto max-w-[520px] border border-line bg-surface p-12 text-center">
          <h1 className="font-serif text-section">Check your email</h1>
          <p className="mt-4 text-model text-ink-soft">
            If <span className="text-ink">{email}</span> has an account, a reset
            link is on its way. It works once and expires in two hours.
          </p>
          <p className="mt-6 text-meta text-ink-mute">
            Nothing arrived? Check the spam folder, or ask us at
            sales@goldridemotors.co.ke.
          </p>
          <Button to="/" size="large" className="mt-8">
            Back to the site
          </Button>
        </div>
      </Page>
    )
  }

  return (
    <Page>
      <div className="mx-auto max-w-[520px]">
        <h1 className="font-serif text-h1">Reset your password</h1>
        <p className="mt-4 text-model text-ink-soft">
          Enter the address you signed up with and we will send you a link to
          choose a new password.
        </p>

        <form onSubmit={handleSubmit} className="mt-10 space-y-6">
          <label className="block">
            <span className="text-badge uppercase text-ink-soft">Email</span>
            <input
              required
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={`mt-3 ${fieldClass}`}
            />
          </label>

          {request.isError && (
            <ul className="border border-line bg-surface p-6">
              {errorMessages(request.error).map((message) => (
                <li key={message} className="text-meta text-ink">
                  {message}
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
            {request.isPending ? 'Sending' : 'Send reset link'}
          </Button>
        </form>
      </div>
    </Page>
  )
}

export default ForgotPassword
