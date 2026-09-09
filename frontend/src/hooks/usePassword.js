import { useMutation } from '@tanstack/react-query'
import api from '../api/client'
import { setToken } from '../lib/auth'

/** Asking for a reset link.
 *
 *  Succeeds whether or not the address has an account - the API answers the
 *  same way either way on purpose, so there is nothing here to branch on and
 *  the screen must not pretend otherwise.
 */
export function useRequestPasswordReset() {
  return useMutation({
    mutationFn: async (email) => {
      const res = await api.post('/api/auth/password/reset/', { email })
      return res.data
    },
  })
}

/** Spending a reset link. */
export function useResetPassword() {
  return useMutation({
    mutationFn: async ({ token, password }) => {
      const res = await api.post('/api/auth/password/reset/confirm/', {
        token,
        password,
      })
      return res.data
    },
  })
}

/** Changing a password you already know.
 *
 *  The API revokes every token on the account and returns a fresh one, so the
 *  reply has to be stored or this tab signs itself out mid-change.
 */
export function useChangePassword() {
  return useMutation({
    mutationFn: async ({ currentPassword, password }) => {
      const res = await api.post('/api/auth/password/change/', {
        current_password: currentPassword,
        password,
      })
      return res.data
    },
    onSuccess: (data) => {
      if (data?.token) setToken(data.token)
    },
  })
}
