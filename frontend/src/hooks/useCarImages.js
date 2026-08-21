import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'

/** Gallery photographs for one car.
 *
 *  Uploads go one request per file rather than one request with many: the
 *  endpoint takes a single image, and doing them separately means a photo
 *  that is too large fails on its own instead of taking the whole batch with
 *  it. Sequential rather than parallel so a phone on Kenyan mobile data is
 *  not trying to push eight files at once.
 */
export function useCarImages(carId) {
  const queryClient = useQueryClient()
  const { isManager } = useAuth()

  const query = useQuery({
    queryKey: ['car-images', carId],
    queryFn: async () => {
      const res = await api.get('/api/staff/car-images/', {
        params: { car: carId },
      })
      return res.data.results ?? res.data
    },
    enabled: Boolean(carId),
  })

  // The photo count sits on the car row, and the public pages render these,
  // so both the staff table and the shopfront are stale after any change.
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['car-images', carId] })
    queryClient.invalidateQueries({ queryKey: ['staff-cars'] })
    queryClient.invalidateQueries({ queryKey: ['cars'] })
  }

  const upload = useMutation({
    mutationFn: async (files) => {
      const done = []
      const failed = []

      for (const file of files) {
        const body = new FormData()
        body.append('car', carId)
        body.append('image', file)
        try {
          const res = await api.post('/api/staff/car-images/', body)
          done.push(res.data)
        } catch (error) {
          const detail =
            error?.response?.data?.image?.[0] ?? 'could not be uploaded'
          failed.push(`${file.name}: ${detail}`)
        }
      }

      return { done, failed }
    },
    onSuccess: invalidate,
  })

  const remove = useMutation({
    mutationFn: (imageId) => api.delete(`/api/staff/car-images/${imageId}/`),
    onSuccess: invalidate,
  })

  /** Promote a gallery shot to the card image. A PATCH on the car itself,
   *  not on the image - they are different fields on different models. */
  const setMain = useMutation({
    mutationFn: async ({ url }) => {
      const blob = await (await fetch(url)).blob()
      const body = new FormData()
      body.append('image', blob, 'main.jpg')
      const res = await api.patch(`/api/staff/cars/${carId}/`, body)
      return res.data
    },
    onSuccess: invalidate,
  })

  return { query, upload, remove, setMain, canDelete: isManager }
}
