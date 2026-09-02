import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'

/** The office side of dealers: applications, submissions, dealerships.
 *
 *  Every mutation here is a Manager's - taking on a dealership and publishing
 *  somebody else's car are both commitments - and the API refuses regardless
 *  of what this file allows.
 */

export const APPLICATION_STATES = [
  ['pending', 'Waiting'],
  ['approved', 'Approved'],
  ['rejected', 'Rejected'],
]

function useDecision(path, keys) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ id, action, note = '' }) => {
      const res = await api.post(`${path}${id}/${action}/`, { note })
      return res.data
    },
    onSuccess: () => {
      for (const key of keys) {
        queryClient.invalidateQueries({ queryKey: [key] })
      }
      // An approval publishes a car and closes a ticket, so both lists behind
      // this screen are now wrong.
      queryClient.invalidateQueries({ queryKey: ['staff-tickets'] })
      queryClient.invalidateQueries({ queryKey: ['staff-cars'] })
    },
  })
}

export function useStaffDealerApplications({ status = 'pending' } = {}) {
  const { isSales } = useAuth()

  const query = useQuery({
    queryKey: ['staff-dealer-applications', status],
    queryFn: async () => {
      const params = status ? { status } : {}
      const res = await api.get('/api/staff/dealers/applications/', { params })
      const data = res.data
      return Array.isArray(data) ? { results: data, count: data.length } : data
    },
    enabled: isSales,
  })

  const decide = useDecision('/api/staff/dealers/applications/', [
    'staff-dealer-applications',
    'staff-dealers',
  ])

  return { query, decide }
}

export function useStaffDealerListings({ status = 'submitted' } = {}) {
  const { isSales } = useAuth()

  const query = useQuery({
    queryKey: ['staff-dealer-listings', status],
    queryFn: async () => {
      const params = status ? { status } : {}
      const res = await api.get('/api/staff/dealers/listings/', { params })
      const data = res.data
      return Array.isArray(data) ? { results: data, count: data.length } : data
    },
    enabled: isSales,
  })

  const decide = useDecision('/api/staff/dealers/listings/', [
    'staff-dealer-listings',
  ])

  return { query, decide }
}

export function useStaffDealers() {
  const queryClient = useQueryClient()
  const { isSales } = useAuth()

  const query = useQuery({
    queryKey: ['staff-dealers'],
    queryFn: async () => {
      const res = await api.get('/api/staff/dealers/')
      const data = res.data
      return Array.isArray(data) ? { results: data, count: data.length } : data
    },
    enabled: isSales,
  })

  const update = useMutation({
    mutationFn: async ({ id, ...values }) => {
      const res = await api.patch(`/api/staff/dealers/${id}/`, values)
      return res.data
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['staff-dealers'] }),
  })

  return { query, update }
}
