import { useState } from 'react'
import { useParams } from 'react-router-dom'
import Button from '../components/Button'
import Page from '../components/Page'
import { errorMessages } from '../lib/errors'
import { useResetPassword } from '../hooks/usePassword'

/** Spending a reset link.
 *
 *  Unlike the dealer activation page there is no check-the-link-first request:
 *  reading a reset token is the same act as spending it, and an endpoint that
 *  told you a token was good without using it would be a way to test stolen
 *  links quietly. So the link is only ever proved by using it, and an expired
 *  or already-used one is reported after the form is submitted.
 *
 *  The two-box confirmation is here because the failure it prevents is
 *  expensive: a mistyped password on a reset locks you out of the account you
 *  were in the middle of recovering.
 */

const fieldClass =
  'h-12 w-full border border-line bg-surface px-4 text-model outline-none focus:border-ink'

function ResetPassword() {
  const { token } = useParams()
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')

  const reset = useResetPassword()
  const mismatch = confirmation.length > 0 && password !== confirmation

  function handleSubmit(event) {
    event.preventDefault()
    if (mismatch) return
    reset.mutate({ token, password })
  }

  if (reset.isSuccess) {
    return (
      <Page>
        <div className="mx-auto max-w-[520px] border border-line bg-surface p-12 text-center">
          <h1 className="font-serif text-section">Your password is changed</h1>
          <p className="mt-4 text-model text-ink-soft">
            Sign in with your new password. Anywhere else that was signed in to
            this account has been signed out.
          </p>
          <Button to="/" size="large" className="mt-8">
            Sign in
          </Button>
        </div>
      </Page>
    )
  }

  return (
    <Page>
      <div className="mx-auto max-w-[520px]">
        <h1 className="font-serif text-h1">Choose a new password</h1>
        <p className="mt-4 text-model text-ink-soft">
          At least 12 characters. Either mix upper case, lower case, numbers and
          symbols, or simply use a longer phrase you will remember.
        </p>

        <form onSubmit={handleSubmit} className="mt-10 space-y-6">
          <label className="block">
            <span className="text-badge uppercase text-ink-soft">
              New password
            </span>
            <input
              required
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className={`mt-3 ${fieldClass}`}
            />
          </label>

          <label className="block">
            <span className="text-badge uppercase text-ink-soft">
              Repeat it
            </span>
            <input
              required
              type="password"
              autoComplete="new-password"
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
              className={`mt-3 ${fieldClass}`}
            />
            {mismatch && (
              <span className="mt-2 block text-meta text-ink">
                Those two do not match.
              </span>
            )}
          </label>

          {reset.isError && (
            <ul className="border border-line bg-surface p-6">
              {errorMessages(reset.error).map((message) => (
                <li key={message} className="text-meta text-ink">
                  {message}
                </li>
              ))}
              <li className="mt-3 text-meta text-ink-mute">
                If the link has expired or been used,{' '}
                <a href="/forgot-password" className="underline">
                  ask for a new one
                </a>
                .
              </li>
            </ul>
          )}

          <Button
            size="large"
            className="w-full"
            type="submit"
            disabled={reset.isPending || mismatch}
          >
            {reset.isPending ? 'Saving' : 'Change password'}
          </Button>
        </form>
      </div>
    </Page>
  )
}

export default ResetPassword
