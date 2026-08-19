import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'

/** The shipping stages, in order. Mirrors ImportOrder.STAGE_CHOICES - the
 *  server validates the value, this only decides what to offer next. */
export const STAGES = [
  ['ordered', 'Ordered'],
  ['shipped', 'Shipped'],
  ['at_port', 'At port'],
  ['clearing', 'Clearing'],
  ['delivered', 'Delivered'],
]

export function nextStage(current) {
  const index = STAGES.findIndex(([key]) => key === current)
  return index >= 0 && index < STAGES.length - 1 ? STAGES[index + 1] : null
}

export function useStaffOrders({ stage = '', cancelled = '', page = 1 } = {}) {
  const queryClient = useQueryClient()

  const params = {}
  if (stage) params.current_stage = stage
  if (cancelled) params.cancelled = cancelled
  if (page > 1) params.page = page

  const query = useQuery({
    queryKey: ['staff-orders', stage, cancelled, page],
    queryFn: async () => {
      const res = await api.get('/api/staff/orders/', { params })
      const data = res.data
      return Array.isArray(data)
        ? { results: data, count: data.length, next: null, previous: null }
        : data
    },
  })

  // A stage change is what the customer's tracking page reads, and delivering
  // an order marks its car sold - so the shopfront is stale too.
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['staff-orders'] })
    queryClient.invalidateQueries({ queryKey: ['cars'] })
  }

  /** Advancing is recorded as a milestone, not a field edit. The milestone is
   *  the history the customer sees; the headline stage follows from it on the
   *  server, so writing the stage directly would leave the two disagreeing. */
  const advance = useMutation({
    mutationFn: async ({ orderId, stage: to, note = '' }) => {
      const res = await api.post('/api/staff/milestones/', {
        order: orderId,
        stage: to,
        note,
      })
      return res.data
    },
    onSuccess: invalidate,
  })

  const reactivate = useMutation({
    mutationFn: async ({ orderId, message }) => {
      const res = await api.post(`/api/staff/orders/${orderId}/reactivate/`, {
        message,
      })
      return res.data
    },
    onSuccess: invalidate,
  })

  return { query, advance, reactivate }
}
