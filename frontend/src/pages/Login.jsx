import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import api from '../api/client'
import { setToken } from '../lib/auth'

function Login() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  const login = useMutation({
    mutationFn: async (credentials) => {
      const res = await api.post('/api/auth/login/', credentials)
      return res.data
    },
    onSuccess: (data) => {
      setToken(data.token)
      navigate('/')
    },
  })

  function handleSubmit(event) {
    event.preventDefault()
    login.mutate({ username, password })
  }

  return (
    <div className="mx-auto max-w-[420px] px-5 py-24">
      <h1 className="font-serif text-section">Sign in</h1>

      <form onSubmit={handleSubmit} className="mt-8 space-y-6">
        <div>
          <label htmlFor="username" className="text-meta text-ink-soft">
            Username
          </label>
          <input
            id="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            className="mt-2 h-11 w-full border border-line bg-surface px-4 text-model outline-none focus:border-ink"
          />
        </div>

        <div>
          <label htmlFor="password" className="text-meta text-ink-soft">
            Password
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="mt-2 h-11 w-full border border-line bg-surface px-4 text-model outline-none focus:border-ink"
          />
        </div>

        {login.isError && (
          <p className="text-meta">Incorrect username or password.</p>
        )}

        <button
          type="submit"
          disabled={login.isPending}
          className="h-12 w-full bg-ink text-badge uppercase text-surface disabled:opacity-50"
        >
          {login.isPending ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}

export default Login