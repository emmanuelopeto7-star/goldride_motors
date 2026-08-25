import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'

/** The one staff queue: approvals and sourcing requests in a single list.
 *
 *  Ownership is the point. Before tickets, two agents could work the same
 *  purchase request and neither would know, because the queue was a list with
 *  no notion of who had what.
 */
export function useTickets({ kind = '', status = '', mine = false, page = 1 } = {}) {
  const params = {}
  if (kind) params.kind = kind
  if (status) params.status = status
  if (mine) params.mine = 'true'
  if (page > 1) params.page = page

  return useQuery({
    queryKey: ['tickets', kind, status, mine, page],
    queryFn: async () => {
      const res = await api.get('/api/staff/tickets/', { params })
      return res.data
    },
  })
}

export function useTicket(id) {
  return useQuery({
    queryKey: ['ticket', id],
    queryFn: async () => {
      const res = await api.get(`/api/staff/tickets/${id}/`)
      return res.data
    },
    enabled: Boolean(id),
  })
}

/** Claim, release and close.
 *
 *  Losing a claim is not an error, it is an outcome: somebody else got there
 *  first and the agent needs to be told who, not shown a red box. So the 409
 *  is caught here and returned as `won: false` with the ticket as it now
 *  stands. Every other failure still throws.
 */
export function useTicketActions(id) {
  const queryClient = useQueryClient()

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['tickets'] })
    queryClient.invalidateQueries({ queryKey: ['ticket', id] })
    // The enquiry itself now carries the reply, and the Enquiries screen
    // lists it - both are stale the moment one is sent.
    queryClient.invalidateQueries({ queryKey: ['inquiry'] })
    queryClient.invalidateQueries({ queryKey: ['staff-enquiries'] })
  }

  const claim = useMutation({
    mutationFn: async (ticketId) => {
      try {
        const res = await api.post(`/api/staff/tickets/${ticketId}/claim/`)
        return { won: true, ticket: res.data }
      } catch (error) {
        if (error?.response?.status === 409) {
          return { won: false, ticket: error.response.data }
        }
        throw error
      }
    },
    onSuccess: invalidate,
  })

  const release = useMutation({
    mutationFn: async (ticketId) => {
      const res = await api.post(`/api/staff/tickets/${ticketId}/release/`)
      return res.data
    },
    onSuccess: invalidate,
  })

  const close = useMutation({
    mutationFn: async (ticketId) => {
      const res = await api.post(`/api/staff/tickets/${ticketId}/close/`)
      return res.data
    },
    onSuccess: invalidate,
  })

  /** Answering an enquiry. Refused rather than duplicated: if another agent
   *  got there first the API sends nothing and returns 409, and this hands
   *  back `sent: false` so the screen can say so instead of pretending. */
  const reply = useMutation({
    mutationFn: async ({ ticketId, message }) => {
      try {
        const res = await api.post(`/api/staff/tickets/${ticketId}/reply/`, {
          message,
        })
        return { sent: true, ticket: res.data }
      } catch (error) {
        if (error?.response?.status === 409) {
          return { sent: false, ticket: error.response.data }
        }
        throw error
      }
    },
    onSuccess: invalidate,
  })

  return { claim, release, close, reply }
}
