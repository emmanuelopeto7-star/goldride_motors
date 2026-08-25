import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'

/** Staff accounts - who can sign in to the dashboard and what they may do.
 *
 *  Removing somebody deactivates their account rather than deleting it: their
 *  name is on decisions, and the API has no DELETE at all. "Remove" here means
 *  they can no longer sign in, which is what it needs to mean.
 */
export function useTeam() {
  const queryClient = useQueryClient()

  const query = useQuery({
    queryKey: ['team'],
    queryFn: async () => {
      const res = await api.get('/api/staff/team/')
      return res.data
    },
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['team'] })

  const add = useMutation({
    mutationFn: async (values) => {
      const res = await api.post('/api/staff/team/', values)
      return res.data
    },
    onSuccess: invalidate,
  })

  const update = useMutation({
    mutationFn: async ({ id, ...fields }) => {
      const res = await api.patch(`/api/staff/team/${id}/`, fields)
      return res.data
    },
    onSuccess: invalidate,
  })

  return { query, add, update }
}
