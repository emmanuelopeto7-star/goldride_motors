import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'

/** How many days before expiry a listing starts asking for attention. Early
 *  enough to renew in a weekly pass, not so early that everything is amber. */
export const EXPIRING_SOON_DAYS = 10

export function daysUntilExpiry(car) {
  if (!car.expires_at) return null
  const ms = new Date(car.expires_at) - Date.now()
  return Math.ceil(ms / 86400000)
}

/** Live, expiring, or already gone. The renewal worklist is built from this. */
export function expiryState(car) {
  if (!car.expires_at) return 'never'
  if (car.is_expired) return 'expired'
  return daysUntilExpiry(car) <= EXPIRING_SOON_DAYS ? 'soon' : 'live'
}

export function useStaffCars({
  search = '',
  expired = '',
  availability = '',
  page = 1,
} = {}) {
  const queryClient = useQueryClient()

  const params = {}
  if (search) params.search = search
  if (expired) params.expired = expired
  if (availability) params.availability = availability
  if (page > 1) params.page = page

  const query = useQuery({
    // The whole payload, not just results - a table showing the first twelve
    // of forty-eight with no way to reach the rest is worse than no table.
    queryKey: ['staff-cars', search, expired, availability, page],
    queryFn: async () => {
      const res = await api.get('/api/staff/cars/', { params })
      const data = res.data
      return Array.isArray(data)
        ? { results: data, count: data.length, next: null, previous: null }
        : data
    },
  })

  // Renewing or editing changes what the public site serves, so the shopfront
  // caches are stale too - an expired car reappearing is the whole point.
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['staff-cars'] })
    queryClient.invalidateQueries({ queryKey: ['cars'] })
    queryClient.invalidateQueries({ queryKey: ['makes'] })
  }

  const extend = useMutation({
    mutationFn: async ({ id, days }) => {
      const res = await api.post(
        `/api/staff/cars/${id}/extend/`,
        days ? { days } : {},
      )
      return res.data
    },
    onSuccess: invalidate,
  })

  const update = useMutation({
    mutationFn: async ({ id, ...fields }) => {
      const res = await api.patch(`/api/staff/cars/${id}/`, fields)
      return res.data
    },
    onSuccess: invalidate,
  })

  return { query, extend, update }
}
