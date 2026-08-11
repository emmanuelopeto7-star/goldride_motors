import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import api from '../api/client'
import { setToken } from '../lib/auth'
import Modal from './Modal'

function AuthModal({ onClose, onSignedIn }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const login = useMutation({
    mutationFn: async (credentials) => {
      const res = await api.post('/api/auth/login/email/', credentials)
      return res.data
    },
     onSuccess: (data) => {
      setToken(data.token)
      onSignedIn()
      onClose()
    },
  })
   function handleSubmit(event) {
    event.preventDefault()
    login.mutate({ email, password })
  }

  return (
    <Modal onClose={onClose}>
      <h2 className="text-center font-serif text-section">Log In or Sign Up</h2>

      <form onSubmit={handleSubmit} className="mt-8 space-y-4">
        <input
          type="email"
          aria-label="Email"
          placeholder="Email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className="h-12 w-full border border-line bg-surface px-4 text-model outline-none focus:border-ink"
        />

        <input
          type="password"
          aria-label="Password"
          placeholder="Password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className="h-12 w-full border border-line bg-surface px-4 text-model outline-none focus:border-ink"
        />
         {login.isError && (
          <p className="text-meta">Incorrect email or password.</p>
        )}

        <button
          type="submit"
          disabled={login.isPending}
          className="h-12 w-full bg-ink text-badge uppercase text-surface disabled:opacity-50"
        >
          {login.isPending ? 'Signing in…' : 'Continue'}
        </button>
      </form>
    </Modal>
  )
}

export default AuthModal