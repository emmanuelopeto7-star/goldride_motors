import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'

/** The oldest model year Kenya will still clear.
 *
 *  Duplicated from the backend deliberately: the server is the authority and
 *  refuses anything older, but telling someone their car is ineligible while
 *  they are still typing is far better than after they submit. Kept as one
 *  constant so there is a single place to change if the rule moves.
 */
export const MAX_VEHICLE_AGE_YEARS = 7

export function earliestEligibleYear() {
  return new Date().getFullYear() - MAX_VEHICLE_AGE_YEARS
}

/** Raise an import request. Public - no account needed. */
export function useCreateImportRequest() {
  return useMutation({
    mutationFn: async (values) => {
      const res = await api.post('/api/imports/requests/', values)
      return res.data
    },
  })
}

/** One request and whatever has been sourced against it.
 *
 *  The token in the URL is the credential, the same arrangement as order
 *  tracking - which is why this needs no auth and why the API withholds our
 *  cost basis from what it returns.
 */
export function useImportRequest(token) {
  const queryClient = useQueryClient()

  const query = useQuery({
    queryKey: ['import-request', token],
    queryFn: async () => {
      const res = await api.get(`/api/imports/requests/${token}/`)
      return res.data
    },
    enabled: Boolean(token),
    retry: false,
  })

  const decide = useMutation({
    mutationFn: async ({ unitId, decision, reason = '' }) => {
      const res = await api.post(
        `/api/imports/requests/${token}/units/${unitId}/decide/`,
        { decision, reason },
      )
      return res.data
    },
    onSuccess: (data) => {
      // The response is the whole request in its new state, and selecting one
      // unit rejects the others - so seed the cache rather than refetching, or
      // the siblings visibly flip a moment later.
      queryClient.setQueryData(['import-request', token], data)
    },
  })

  return { query, decide }
}
