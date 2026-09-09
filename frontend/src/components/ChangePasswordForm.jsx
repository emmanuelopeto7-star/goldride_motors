import { useState } from 'react'
import Button from './Button'
import { errorMessages } from '../lib/errors'
import { useChangePassword } from '../hooks/usePassword'

/** Changing a password from inside the account.
 *
 *  Asks for the current one even though the caller is already signed in: the
 *  case worth stopping is a borrowed laptop or a stolen token, and without it
 *  either of those converts straight into a permanently stolen account.
 *
 *  The API revokes every token on success and returns a fresh one, which the
 *  hook stores - so this tab stays signed in and every other device does not.
 */

const fieldClass =
  'h-12 w-full max-w-[420px] border border-line bg-surface px-4 text-model outline-none focus:border-ink'

function ChangePasswordForm() {
  const [currentPassword, setCurrentPassword] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')

  const change = useChangePassword()
  const mismatch = confirmation.length > 0 && password !== confirmation

  function handleSubmit(event) {
    event.preventDefault()
    if (mismatch) return
    change.mutate(
      { currentPassword, password },
      {
        onSuccess: () => {
          setCurrentPassword('')
          setPassword('')
          setConfirmation('')
        },
      },
    )
  }

  return (
    <form onSubmit={handleSubmit} className="mt-6 space-y-4">
      <label className="block">
        <span className="text-badge uppercase text-ink-soft">
          Current password
        </span>
        <input
          required
          type="password"
          autoComplete="current-password"
          value={currentPassword}
          onChange={(event) => setCurrentPassword(event.target.value)}
          className={`mt-2 ${fieldClass}`}
        />
      </label>

      <label className="block">
        <span className="text-badge uppercase text-ink-soft">New password</span>
        <input
          required
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className={`mt-2 ${fieldClass}`}
        />
        <span className="mt-2 block text-meta text-ink-mute">
          At least 12 characters. Mix upper case, lower case, numbers and
          symbols — or use a longer phrase you will remember.
        </span>
      </label>

      <label className="block">
        <span className="text-badge uppercase text-ink-soft">Repeat it</span>
        <input
          required
          type="password"
          autoComplete="new-password"
          value={confirmation}
          onChange={(event) => setConfirmation(event.target.value)}
          className={`mt-2 ${fieldClass}`}
        />
        {mismatch && (
          <span className="mt-2 block text-meta text-ink">
            Those two do not match.
          </span>
        )}
      </label>

      {change.isError && (
        <ul className="max-w-[420px] space-y-1">
          {errorMessages(change.error).map((message) => (
            <li key={message} className="text-meta text-ink">
              {message}
            </li>
          ))}
        </ul>
      )}

      {change.isSuccess && (
        <p className="text-meta text-ink-soft">
          Password changed. Every other device has been signed out.
        </p>
      )}

      <Button type="submit" disabled={change.isPending || mismatch}>
        {change.isPending ? 'Saving…' : 'Change password'}
      </Button>
    </form>
  )
}

export default ChangePasswordForm
