import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'

/** The rates the live calculator runs on. Cached hard - they change about
 *  once a budget cycle, and refetching them per keystroke would be absurd. */
export function useImportRates() {
  return useQuery({
    queryKey: ['import-rates'],
    queryFn: async () => {
      const res = await api.get('/api/staff/import-rates/')
      return res.data
    },
    staleTime: Infinity,
  })
}

/** The sourcing worklist: requests waiting for units. */
export function useImportRequests(status = '') {
  return useQuery({
    queryKey: ['staff-import-requests', status],
    queryFn: async () => {
      const res = await api.get('/api/staff/import-requests/', {
        params: status ? { status } : undefined,
      })
      return res.data.results ?? res.data
    },
  })
}

/** One request, plus everything you can do to it from the sourcing screen. */
export function useImportRequestDetail(id) {
  const queryClient = useQueryClient()
  const key = ['staff-import-request', id]

  const query = useQuery({
    queryKey: key,
    queryFn: async () => {
      const res = await api.get(`/api/staff/import-requests/${id}/`)
      return res.data
    },
    enabled: Boolean(id),
  })

  // Adding the first unit flips the request from pending to sourcing, and
  // notifying flips it again - so the request itself is stale after each,
  // not just its list of units.
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: key })
    queryClient.invalidateQueries({ queryKey: ['staff-import-requests'] })
  }

  const addUnit = useMutation({
    mutationFn: async (values) => {
      const res = await api.post('/api/staff/sourced-units/', {
        ...values,
        request: id,
      })
      return res.data
    },
    onSuccess: invalidate,
  })

  /** Correcting a unit after it was saved - a mistyped dollar rate or a
   *  clearing charge that came in higher. Selection and push stay on their
   *  own endpoints, so this cannot change a unit's status by accident. */
  const updateUnit = useMutation({
    mutationFn: async ({ unitId, ...values }) => {
      const res = await api.patch(`/api/staff/sourced-units/${unitId}/`, values)
      return res.data
    },
    onSuccess: invalidate,
  })

  const notify = useMutation({
    mutationFn: async () => {
      const res = await api.post(`/api/staff/import-requests/${id}/notify/`)
      return res.data
    },
    onSuccess: invalidate,
  })

  const pushToStock = useMutation({
    mutationFn: async ({ unitId, markup_percent }) => {
      const res = await api.post(
        `/api/staff/sourced-units/${unitId}/push-to-stock/`,
        markup_percent ? { markup_percent } : {},
      )
      return res.data
    },
    onSuccess: () => {
      invalidate()
      // A new listing exists now, so the public catalogue is stale too.
      queryClient.invalidateQueries({ queryKey: ['cars'] })
    },
  })

  return { query, addUnit, updateUnit, notify, pushToStock }
}
