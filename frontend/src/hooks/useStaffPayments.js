import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'

export const STATUSES = [
  ['pending', 'Pending'],
  ['paid', 'Paid'],
  ['failed', 'Failed'],
  ['refunded', 'Refunded'],
]

export function useStaffPayments({ status = '', method = '', page = 1 } = {}) {
  const queryClient = useQueryClient()
  const { isManager } = useAuth()

  const params = {}
  if (status) params.status = status
  if (method) params.method = method
  if (page > 1) params.page = page

  const query = useQuery({
    queryKey: ['staff-payments', status, method, page],
    queryFn: async () => {
      const res = await api.get('/api/staff/payments/', { params })
      const data = res.data
      return Array.isArray(data)
        ? { results: data, count: data.length, next: null, previous: null }
        : data
    },
  })

  // A payment moving to paid changes an order's balance, so the orders list
  // is stale alongside this one.
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['staff-payments'] })
    queryClient.invalidateQueries({ queryKey: ['staff-orders'] })
  }

  /** Send a checkout link or an M-PESA prompt, and email the instructions.
   *  Manager only - it is the act of asking someone for money. */
  const dispatchPayment = useMutation({
    mutationFn: async ({ reference, email, phone }) => {
      const res = await api.post(`/api/staff/payments/${reference}/dispatch/`, {
        email,
        phone,
      })
      return res.data
    },
    onSuccess: invalidate,
  })

  /** Ask the provider what actually happened.
   *
   *  Not a refresh button. Webhooks get dropped, and reconciliation has
   *  already caught real payments that were taken but never recorded - which
   *  is why it is offered to Sales and not held behind a manager.
   */
  const reconcileOne = useMutation({
    mutationFn: async (reference) => {
      const res = await api.post(`/api/staff/payments/${reference}/reconcile/`)
      return res.data
    },
    onSuccess: invalidate,
  })

  const reconcileAll = useMutation({
    mutationFn: async () => {
      const res = await api.post('/api/staff/payments/reconcile/')
      return res.data
    },
    onSuccess: invalidate,
  })

  return {
    query,
    dispatchPayment,
    reconcileOne,
    reconcileAll,
    canDispatch: isManager,
  }
}
