import { createContext, useContext, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import { getToken, setToken, clearToken } from '../lib/auth'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const queryClient = useQueryClient()

  // localStorage is not reactive - writing to it re-renders nothing. This
  // mirror is what makes the query fire the moment someone signs in.
  const [token, setTokenState] = useState(getToken())

  const { data: user, isPending } = useQuery({
    // A different token is a different identity, so it gets its own cache entry.
    queryKey: ['me', token],
    queryFn: async () => {
      const res = await api.get('/api/me/')
      return res.data
    },
    enabled: Boolean(token),
    // A 401 will never succeed by trying again; retrying just delays the truth.
    retry: false,
  })

  function signIn(newToken) {
    setToken(newToken)
    setTokenState(newToken)
  }

  async function signOut() {
    try {
      await api.post('/api/auth/logout/')
    } catch {
      // The token may already be dead server-side. Destroying it there is the
      // important half, but a network error must not strand us signed in here.
    }
    clearToken()
    setTokenState(null)
    queryClient.removeQueries({ queryKey: ['me'] })
  }

  const roles = user?.roles ?? []

  // Mirrors goldride_app/permissions.py exactly. A superuser passes IsSales
  // and IsManager on the server, so a route guard that ignores that lets an
  // account call every staff endpoint in the API while being bounced from the
  // screen built on top of them. IsCustomer has no such bypass and neither
  // does isCustomer here - a superuser is not a buyer.
  const superuser = Boolean(user?.is_superuser)

  const value = {
    user: user ?? null,
    isLoading: Boolean(token) && isPending,
    roles,
    isCustomer: roles.includes('Customer'),
    isSales: superuser || roles.includes('Sales') || roles.includes('Manager'),
    isManager: superuser || roles.includes('Manager'),
    isStaff: Boolean(user?.is_staff) || superuser,
    needsEmail: Boolean(user?.needs_email),
    emailVerified: Boolean(user?.email_verified),
    hasPassword: Boolean(user?.has_password),
    providers: user?.providers ?? [],
    signIn,
    signOut,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === null) {
    // Names the mistake instead of failing as a confusing null deref deeper in.
    throw new Error('useAuth must be used inside AuthProvider')
  }
  return context
}
