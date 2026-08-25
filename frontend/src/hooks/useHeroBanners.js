import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'

/** The home page hero, which until now could only be changed in the Django
 *  admin. Several banners may be active at once - the most recently updated
 *  of them is the one on the site, and the API says which with `is_live`.
 */
export function useHeroBanners() {
  const queryClient = useQueryClient()

  const query = useQuery({
    queryKey: ['hero-banners'],
    queryFn: async () => {
      const res = await api.get('/api/staff/hero-banners/')
      return res.data
    },
  })

  // The public hero is served from the same rows, so the shopfront's copy is
  // stale the moment any of this changes.
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['hero-banners'] })
    queryClient.invalidateQueries({ queryKey: ['hero'] })
  }

  const create = useMutation({
    mutationFn: async ({ image, video, ...fields }) => {
      // Always multipart: a hero without its poster frame is not a hero, so
      // there is no JSON path worth keeping here.
      const form = new FormData()
      Object.entries(fields).forEach(([key, value]) => {
        if (value !== '' && value != null) form.append(key, value)
      })
      if (image) form.append('image', image)
      if (video) form.append('video', video)
      const res = await api.post('/api/staff/hero-banners/', form)
      return res.data
    },
    onSuccess: invalidate,
  })

  const update = useMutation({
    mutationFn: async ({ id, ...fields }) => {
      const res = await api.patch(`/api/staff/hero-banners/${id}/`, fields)
      return res.data
    },
    onSuccess: invalidate,
  })

  const remove = useMutation({
    mutationFn: (id) => api.delete(`/api/staff/hero-banners/${id}/`),
    onSuccess: invalidate,
  })

  return { query, create, update, remove }
}
