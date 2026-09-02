import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'

export const STATUSES = [
  ['pending', 'Pending'],
  ['paid', 'Paid'],
  ['failed', 'Failed'],
  ['refunded', 'Refunded'],
]

/** How the money is meant to arrive. Mirrors Payment.METHOD_CHOICES.
 *  Named for what staff call them, not for what the column stores. */
export const METHODS = [
  ['card', 'Card'],
  ['mpesa', 'M-PESA'],
  ['manual', 'Bank transfer'],
]

/** Safaricom's per-transaction ceiling. Mirrors MPESA_TRANSACTION_LIMIT in
 *  payments/dispatch.py, which refuses anything above it - this only lets the
 *  form say so before the amount is typed rather than after it is sent. */
export const MPESA_LIMIT = 250000

export function useStaffPayments({ status = '', method = '', page = 1 } = {}) {
  const queryClient = useQueryClient()
  const { isManager, isSales } = useAuth()

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
   *  The amount is not chosen here - it was fixed when the invoice was
   *  raised - so this is chasing, not deciding. */
  /** Raise an invoice by hand.
   *
   *  Approving a purchase raises one for us; everything else - a balance, a
   *  second instalment, an order that was never a purchase request - had no
   *  way in at all, so those amounts existed nowhere the app could collect
   *  them. What may be asked for is bounded by the order's outstanding
   *  balance, so this cannot invent a debt.
   *
   *  It does not ask anyone for the money. That stays a second, deliberate
   *  step, so a mistyped figure can be seen before it reaches a phone.
   */
  const createPayment = useMutation({
    mutationFn: async ({ order, amount, method, note = '' }) => {
      const res = await api.post('/api/staff/payments/', {
        order,
        amount,
        method,
        note,
      })
      return res.data
    },
    onSuccess: invalidate,
  })

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
  /** Say a bank transfer arrived.
   *
   *  Manager only, and narrower than raising or chasing on purpose. Those ask
   *  for money an agreed order total already says is owed; this asserts that
   *  money landed, with no provider standing behind the assertion - so the
   *  API refuses it for card and M-PESA, which can be asked instead.
   */
  const recordPayment = useMutation({
    mutationFn: async ({ reference, provider_ref, note = '' }) => {
      const res = await api.post(`/api/staff/payments/${reference}/record/`, {
        provider_ref,
        note,
      })
      return res.data
    },
    onSuccess: invalidate,
  })

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

  const correctPayment = useMutation({
    mutationFn: async ({ reference, status, reason }) => {
      const res = await api.post(
        `/api/staff/payments/${reference}/correct/`,
        { status, reason },
      )
      return res.data
    },
    onSuccess: (_data, variables) => {
      invalidate()
      // The history is the whole point of a correction, and it is one request
      // behind until this lands.
      queryClient.invalidateQueries({
        queryKey: ['payment-history', variables.reference],
      })
    },
  })

  return {
    query,
    createPayment,
    dispatchPayment,
    reconcileOne,
    reconcileAll,
    correctPayment,
    // Sales, not just a manager. Raising an invoice and chasing it is the
    // job; the decisions about the money - approving a purchase, the rates,
    // deleting anything - are what stay with a manager.
    recordPayment,
    canDispatch: isSales,
    canRaise: isSales,
    canRecord: isManager,
    // Overruling what a provider said is a manager's alone. Reading the
    // history is not - an agent fielding "I paid on Tuesday" needs it.
    canCorrect: isManager,
  }
}

/** Everything that has ever happened to one payment.
 *
 *  Fetched on demand rather than with the list: a page of twelve payments
 *  would otherwise pull twelve histories nobody has asked to see.
 */
export function usePaymentHistory(reference) {
  const { isSales } = useAuth()

  return useQuery({
    queryKey: ['payment-history', reference],
    queryFn: async () => {
      const res = await api.get(`/api/staff/payments/${reference}/history/`)
      return res.data
    },
    enabled: isSales && Boolean(reference),
  })
}

/** Whether the automatic sweep is alive, and what it last did.
 *
 *  "Checked 6 minutes ago" is the difference between trusting this screen and
 *  quietly not - a sweep that silently stopped looks exactly like a quiet week.
 */
export function useReconciliationRuns() {
  const { isSales } = useAuth()

  return useQuery({
    queryKey: ['reconciliation-runs'],
    queryFn: async () => {
      const res = await api.get('/api/staff/payments/reconciliation-runs/')
      return res.data
    },
    enabled: isSales,
    refetchInterval: 60_000,
  })
}
