import { useState } from 'react'
import { useParams } from 'react-router-dom'
import Button from '../components/Button'
import Page from '../components/Page'
import { errorMessages } from '../lib/errors'
import { useActivationLink, useSetDealerPassword } from '../hooks/useDealer'

/** Setting the password on a newly approved dealer account.
 *
 *  The account exists but has no usable password - nobody here ever knew one,
 *  which is the point: a generated password sent by email is a password living
 *  in an inbox forever. The link is checked before the form is shown, so an
 *  expired one says so rather than failing after a password has been typed.
 */

const fieldClass =
  'h-12 w-full border border-line bg-surface px-4 text-model outline-none focus:border-ink'

function DealerActivate() {
  const { token } = useParams()
  const [password, setPassword] = useState('')

  const link = useActivationLink(token)
  const setup = useSetDealerPassword(token)

  function handleSubmit(event) {
    event.preventDefault()
    setup.mutate(password)
  }

  // Said here rather than by redirecting to the home page: they are not
  // signed in yet, so a bounce to the storefront is a dead end that never
  // mentions the password they just set.
  if (setup.isSuccess) {
    return (
      <Page>
        <div className="mx-auto max-w-[520px] border border-line bg-surface p-12 text-center">
          <h1 className="font-serif text-section">Your password is set</h1>
          <p className="mt-4 text-model text-ink-soft">
            Sign in with {link.data?.email} and your new password to start
            submitting cars.
          </p>
          <Button to="/" size="large" className="mt-8">
            Sign in
          </Button>
        </div>
      </Page>
    )
  }

  if (link.isLoading) {
    return (
      <Page>
        <div className="mx-auto h-64 w-full max-w-[520px] animate-pulse bg-line" />
      </Page>
    )
  }

  if (link.isError) {
    return (
      <Page>
        <div className="mx-auto max-w-[520px] border border-line bg-surface p-12 text-center">
          <h1 className="font-serif text-section">This link cannot be used</h1>
          <p className="mt-4 text-model text-ink-soft">
            {errorMessages(link.error)[0]}
          </p>
          <p className="mt-6 text-meta text-ink-mute">
            Ask us for a new one at sales@goldridemotors.co.ke.
          </p>
        </div>
      </Page>
    )
  }

  return (
    <Page>
      <div className="mx-auto max-w-[520px]">
        <h1 className="font-serif text-h1">Set your password</h1>
        <p className="mt-4 text-model text-ink-soft">
          Your dealer account is ready. Choose a password for{' '}
          <span className="text-ink">{link.data.email}</span> and you can start
          submitting cars.
        </p>

        <form onSubmit={handleSubmit} className="mt-10 space-y-6">
          <label className="block">
            <span className="text-badge uppercase text-ink-soft">Password</span>
            <input
              required
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className={`mt-3 ${fieldClass}`}
            />
          </label>

          {setup.isError && (
            <ul className="border border-line bg-surface p-6">
              {errorMessages(setup.error).map((message) => (
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
            disabled={setup.isPending}
          >
            {setup.isPending ? 'Saving' : 'Set password'}
          </Button>
        </form>
      </div>
    </Page>
  )
}

export default DealerActivate
