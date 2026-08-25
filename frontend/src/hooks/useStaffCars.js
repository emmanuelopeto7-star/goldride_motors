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

/** Multipart only when a photograph is attached.
 *
 *  Same reasoning as the sourced-unit form: multipart carries no null, so a
 *  blank optional field would have to travel as the empty string, which DRF
 *  refuses for a number. JSON stays the default and empty values are dropped
 *  either way - a new listing simply takes the model's own defaults for
 *  anything left blank.
 */
function bodyFor(values) {
  const { image, ...rest } = values
  const filled = Object.fromEntries(
    Object.entries(rest).filter(([, value]) => value !== '' && value != null),
  )
  if (!image) return filled

  const form = new FormData()
  Object.entries(filled).forEach(([key, value]) => form.append(key, value))
  form.append('image', image)
  return form
}

export function useStaffCars({
  search = '',
  expired = '',
  availability = '',
  photos = '',
  page = 1,
} = {}) {
  const queryClient = useQueryClient()

  const params = {}
  if (search) params.search = search
  if (expired) params.expired = expired
  if (availability) params.availability = availability
  if (photos) params.photos = photos
  if (page > 1) params.page = page

  const query = useQuery({
    // The whole payload, not just results - a table showing the first twelve
    // of forty-eight with no way to reach the rest is worse than no table.
    queryKey: ['staff-cars', search, expired, availability, photos, page],
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

  const create = useMutation({
    mutationFn: async (values) => {
      const res = await api.post('/api/staff/cars/', bodyFor(values))
      return res.data
    },
    onSuccess: invalidate,
  })

  const remove = useMutation({
    mutationFn: (id) => api.delete(`/api/staff/cars/${id}/`),
    onSuccess: invalidate,
  })

  return { query, extend, update, create, remove }
}
