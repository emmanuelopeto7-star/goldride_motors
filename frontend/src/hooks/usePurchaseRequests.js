import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'

/** The staff purchase-request queue, and the two decisions you can make on it.
 *
 *  Two roles, two different capabilities, and the split is enforced by the API
 *  rather than by us: `GET /api/purchases/staff/` is IsSales, but both
 *  approve and reject are IsManager. Sales can therefore read this whole
 *  screen and act on none of it, which the UI has to say out loud - hence
 *  `canDecide` coming back from the hook.
 *
 *  Approving is not a status change. It creates the ImportOrder, reserves the
 *  car, raises the Payment and dispatches collection, all in one request. That
 *  is why `approve.data` is worth rendering rather than discarding.
 */
export function usePurchaseRequests(status = 'pending') {
  const queryClient = useQueryClient()
  const { isManager } = useAuth()

  const query = useQuery({
    // status is part of the key, so switching filters refetches rather than
    // showing the previous list under the new heading.
    queryKey: ['staff-purchase-requests', status],
    queryFn: async () => {
      const res = await api.get('/api/purchases/staff/', {
        params: status ? { status } : undefined,
      })
      return res.data.results ?? res.data
    },
  })

  // A decision moves a car to reserved and can raise a payment, so the lists
  // that show cars and orders are stale the moment one lands.
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['staff-purchase-requests'] })
    queryClient.invalidateQueries({ queryKey: ['cars'] })
    queryClient.invalidateQueries({ queryKey: ['my-orders'] })
  }

  const approve = useMutation({
    mutationFn: async ({ id, note = '' }) => {
      const res = await api.post(`/api/purchases/staff/${id}/approve/`, { note })
      return res.data
    },
    onSuccess: invalidate,
  })

  const reject = useMutation({
    mutationFn: async ({ id, note = '' }) => {
      const res = await api.post(`/api/purchases/staff/${id}/reject/`, { note })
      return res.data
    },
    onSuccess: invalidate,
  })

  return { query, approve, reject, canDecide: isManager }
}

/** What actually happened, in a sentence, from an approve response.
 *
 *  Approval and collection are separate outcomes and the second one fails
 *  routinely at these prices: Paystack refuses large amounts outright and
 *  M-PESA caps at 250,000, so on most of this inventory `dispatched` comes
 *  back false and the payment falls to manual. Reading that as "approval
 *  failed" would be wrong - the order exists and the car is reserved either
 *  way. Only the collection needs a human.
 */
export function describeApproval(result) {
  if (!result) return null

  if (result.dispatched && result.checkout_url) {
    return {
      tone: 'done',
      message: 'Approved. Checkout link sent to the customer.',
      checkoutUrl: result.checkout_url,
    }
  }

  if (result.dispatched) {
    return { tone: 'done', message: `Approved. ${result.detail}` }
  }

  return {
    tone: 'manual',
    message:
      `Approved, but collection could not be sent automatically: ` +
      `${result.detail}. The order stands and the car is reserved - arrange ` +
      `payment by bank transfer.`,
  }
}
