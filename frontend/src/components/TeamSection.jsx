import { useState } from 'react'
import ConfirmModal from './ConfirmModal'
import ErrorState from './ErrorState'
import { errorMessages } from '../lib/errors'
import { useAuth } from '../context/AuthContext'
import { useTeam } from '../hooks/useTeam'
import Button from './Button'

const fieldClass =
  'h-12 w-full border border-line bg-surface px-4 text-model outline-none focus:border-ink'
const labelClass = 'text-badge uppercase text-ink-soft'

const BLANK = {
  first_name: '',
  last_name: '',
  username: '',
  email: '',
  role: 'Sales',
  password: '',
}

/** Who can sign in to the dashboard, and what they may do.
 *
 *  Removing somebody switches their account off rather than deleting it -
 *  their name is on approvals and replies, and that record has to stay
 *  readable. Nobody can act on their own account, which is what stops the
 *  last manager locking the whole team out.
 */
function TeamSection() {
  const { query, add, update } = useTeam()
  const { user } = useAuth()
  const [adding, setAdding] = useState(false)
  const [values, setValues] = useState(BLANK)
  const [removing, setRemoving] = useState(null)

  function set(field) {
    return (event) =>
      setValues((current) => ({ ...current, [field]: event.target.value }))
  }

  function handleSubmit(event) {
    event.preventDefault()
    add.mutate(values, {
      onSuccess: () => {
        setValues(BLANK)
        setAdding(false)
      },
    })
  }

  const team = query.data ?? []

  return (
    <section className="mt-16 border-t border-line pt-12">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="font-serif text-section">The team</h2>
          <p className="mt-1 text-meta text-ink-soft">
            Who can sign in to this dashboard, and what they may do.
          </p>
        </div>
        <Button
          variant="secondary"
          onClick={() => {
            add.reset()
            setAdding((open) => !open)
          }}
        >
          {adding ? 'Cancel' : 'Add someone'}
        </Button>
      </div>

      {adding && (
        <form onSubmit={handleSubmit} className="mt-6 border border-line bg-surface p-6">
          <div className="grid gap-6 sm:grid-cols-2">
            <div>
              <label htmlFor="t-first" className={labelClass}>First name</label>
              <input id="t-first" required value={values.first_name} onChange={set('first_name')} className={`mt-2 ${fieldClass}`} />
            </div>
            <div>
              <label htmlFor="t-last" className={labelClass}>Surname</label>
              <input id="t-last" required value={values.last_name} onChange={set('last_name')} className={`mt-2 ${fieldClass}`} />
            </div>
            <div>
              <label htmlFor="t-username" className={labelClass}>Username</label>
              <input id="t-username" required value={values.username} onChange={set('username')} className={`mt-2 ${fieldClass}`} placeholder="asha" />
            </div>
            <div>
              <label htmlFor="t-email" className={labelClass}>Email</label>
              <input id="t-email" type="email" required value={values.email} onChange={set('email')} className={`mt-2 ${fieldClass}`} />
            </div>
            <div>
              <label htmlFor="t-role" className={labelClass}>Role</label>
              <select id="t-role" value={values.role} onChange={set('role')} className={`mt-2 ${fieldClass}`}>
                <option value="Sales">Sales</option>
                <option value="Manager">Manager</option>
              </select>
              <p className="mt-2 text-meta text-ink-mute">
                Sales works the queue and the stock. A Manager also approves
                sales, sets the rates and deletes.
              </p>
            </div>
            <div>
              <label htmlFor="t-password" className={labelClass}>First password</label>
              <input id="t-password" type="password" required value={values.password} onChange={set('password')} className={`mt-2 ${fieldClass}`} />
              <p className="mt-2 text-meta text-ink-mute">
                Hand it to them in person. They can change it from their own
                account.
              </p>
            </div>
          </div>

          {add.isError && (
            <ul className="mt-6">
              {errorMessages(add.error).map((message) => (
                <li key={message} className="text-meta text-ink">{message}</li>
              ))}
            </ul>
          )}

          <Button
            size="large"
            className="mt-6"
            type="submit"
            disabled={add.isPending}
          >
            {add.isPending ? 'Adding...' : 'Add them'}
          </Button>
        </form>
      )}

      <div className="mt-6">
        {query.isPending ? (
          <div className="h-32 w-full animate-pulse bg-line" />
        ) : query.isError ? (
          <ErrorState message="We could not load the team." onRetry={query.refetch} />
        ) : (
          <ul className="space-y-3">
            {team.map((member) => {
              const isMe = member.username === user?.username
              return (
                <li
                  key={member.id}
                  className={`flex flex-wrap items-center justify-between gap-x-8 gap-y-3 border border-line p-4 ${
                    member.is_active ? 'bg-surface' : 'bg-transparent'
                  }`}
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-3">
                      <p className="text-model">
                        {member.full_name || member.username}
                      </p>
                      <span className="rounded-full border border-line px-3 py-1 text-badge uppercase text-ink-soft">
                        {member.role ?? 'No role'}
                      </span>
                      {!member.is_active && (
                        <span className="text-meta text-ink-mute">Switched off</span>
                      )}
                      {isMe && <span className="text-meta text-ink-mute">You</span>}
                    </div>
                    <p className="mt-1 text-meta text-ink-soft">
                      {member.username} · {member.email || 'no email'} ·{' '}
                      {member.last_login
                        ? `last in ${new Date(member.last_login).toLocaleDateString('en-KE')}`
                        : 'never signed in'}
                    </p>
                  </div>

                  {/* Nobody may act on their own account, and the owner's is
                      managed in Django admin - the API refuses both, so the
                      controls are not offered either. */}
                  {!isMe && !member.is_superuser && (
                    <div className="flex flex-wrap items-center gap-4">
                      <button
                        type="button"
                        disabled={update.isPending}
                        onClick={() =>
                          update.mutate({
                            id: member.id,
                            role: member.role === 'Manager' ? 'Sales' : 'Manager',
                          })
                        }
                        className="text-meta text-ink underline disabled:opacity-50"
                      >
                        {member.role === 'Manager' ? 'Make sales' : 'Make manager'}
                      </button>
                      <button
                        type="button"
                        disabled={update.isPending}
                        onClick={() => {
                          update.reset()
                          if (member.is_active) setRemoving(member)
                          else update.mutate({ id: member.id, is_active: true })
                        }}
                        className="text-meta text-ink-soft underline disabled:opacity-50"
                      >
                        {member.is_active ? 'Remove' : 'Bring back'}
                      </button>
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </div>

      {removing && (
        <ConfirmModal
          title={`Remove ${removing.full_name || removing.username}?`}
          body="They will not be able to sign in. Nothing they approved or answered is lost, and you can bring them back at any time."
          confirmLabel="Remove them"
          mutation={update}
          onConfirm={() =>
            update.mutate(
              { id: removing.id, is_active: false },
              { onSuccess: () => setRemoving(null) },
            )
          }
          onClose={() => setRemoving(null)}
        />
      )}
    </section>
  )
}

export default TeamSection
