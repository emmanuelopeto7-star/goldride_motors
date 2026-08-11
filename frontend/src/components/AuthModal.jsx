import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import api from '../api/client'
import { errorMessages } from '../lib/errors'
import { useAuth } from '../context/AuthContext'
import Modal from './Modal'
import SocialButtons from './SocialButtons'

const fieldClass =
  'h-12 w-full border border-line bg-surface px-4 text-model outline-none focus:border-ink'

function AuthModal({ onClose }) {
  const { signIn } = useAuth()
  const [mode, setMode] = useState('login')
  const [firstName, setFirstName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [socialError, setSocialError] = useState(null)

  const isRegister = mode === 'register'

  const auth = useMutation({
    mutationFn: async () => {
      const url = isRegister ? '/api/auth/register/' : '/api/auth/login/email/'
      const body = isRegister
        ? { first_name: firstName, email, password }
        : { email, password }

      const res = await api.post(url, body)
      return res.data
    },
    onSuccess: (data) => {
      signIn(data.token)
      onClose()
    },
  })

  function handleSubmit(event) {
    event.preventDefault()
    auth.mutate()
  }

  function switchMode() {
    setMode(isRegister ? 'login' : 'register')
    auth.reset()
  }

  return (
    <Modal onClose={onClose}>
      <h2 className="text-center font-serif text-section">Log In or Sign Up</h2>

      <div className="mt-8">
        <SocialButtons
          onSignedIn={(token) => {
            signIn(token)
            onClose()
          }}
          onError={(error) => setSocialError(errorMessages(error)[0])}
        />
      </div>

      {socialError && <p className="mt-4 text-meta">{socialError}</p>}

      <form onSubmit={handleSubmit} className="mt-4 space-y-4">
        {isRegister && (
          <input
            aria-label="First name"
            placeholder="First name"
            value={firstName}
            onChange={(event) => setFirstName(event.target.value)}
            className={fieldClass}
            required
          />
        )}

        <input
          type="email"
          aria-label="Email"
          placeholder="Email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className={fieldClass}
          required
        />

        <input
          type="password"
          aria-label="Password"
          placeholder="Password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className={fieldClass}
          required
        />

        {auth.isError && (
          <ul className="space-y-1">
            {errorMessages(auth.error).map((message) => (
              <li key={message} className="text-meta">
                {message}
              </li>
            ))}
          </ul>
        )}

        <button
          type="submit"
          disabled={auth.isPending}
          className="h-12 w-full bg-ink text-badge uppercase text-surface disabled:opacity-50"
        >
          {auth.isPending
            ? 'Please wait…'
            : isRegister
              ? 'Create account'
              : 'Continue'}
        </button>
      </form>

      <p className="mt-6 text-center text-meta text-ink-soft">
        {isRegister ? 'Already have an account? ' : 'New to Goldride? '}
        <button type="button" onClick={switchMode} className="text-ink underline">
          {isRegister ? 'Sign in' : 'Create an account'}
        </button>
      </p>
    </Modal>
  )
}

export default AuthModal