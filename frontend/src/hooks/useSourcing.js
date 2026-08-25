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

/** Putting new rates in force. A Manager's call - these decide what every
 *  future quote charges - and it adds a row rather than editing one, so an
 *  old quote can still be read back under the rates it was worked out under.
 */
export function useSetImportRates() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (values) => {
      const res = await api.post('/api/staff/import-rates/', values)
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['import-rates'] })
    },
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
/** JSON unless a photograph is attached.
 *
 *  Two paths on purpose. A blank numeric has to travel as `null` to clear it,
 *  and multipart has no null - only the empty string, which DRF rejects for a
 *  decimal field. So the ordinary case keeps sending JSON and keeps clearing
 *  properly; the moment a file is chosen the body becomes FormData and empty
 *  fields are left out rather than cleared.
 */
function bodyFor(values) {
  const { photo, ...rest } = values
  if (!photo) return rest

  const form = new FormData()
  Object.entries(rest).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') {
      form.append(key, value)
    }
  })
  form.append('photo', photo)
  return form
}

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
      const res = await api.post(
        '/api/staff/sourced-units/',
        bodyFor({ ...values, request: id }),
      )
      return res.data
    },
    onSuccess: invalidate,
  })

  /** Correcting a unit after it was saved - a mistyped dollar rate or a
   *  clearing charge that came in higher. Selection and push stay on their
   *  own endpoints, so this cannot change a unit's status by accident. */
  const updateUnit = useMutation({
    mutationFn: async ({ unitId, ...values }) => {
      const res = await api.patch(
        `/api/staff/sourced-units/${unitId}/`,
        bodyFor(values),
      )
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

  /** A unit added by mistake - a duplicate, or one entered against the wrong
   *  request. Manager only, like every other delete. */
  const removeUnit = useMutation({
    mutationFn: (unitId) => api.delete(`/api/staff/sourced-units/${unitId}/`),
    onSuccess: invalidate,
  })

  /** The whole request. Its units go with it, which is why this asks first. */
  const removeRequest = useMutation({
    mutationFn: () => api.delete(`/api/staff/import-requests/${id}/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['staff-import-requests'] })
      queryClient.invalidateQueries({ queryKey: ['tickets'] })
    },
  })

  return { query, addUnit, updateUnit, notify, pushToStock, removeUnit, removeRequest }
}
