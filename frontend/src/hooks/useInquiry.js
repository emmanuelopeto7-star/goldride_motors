import { useQuery } from '@tanstack/react-query'
import api from '../api/client'

/** One enquiry, for the ticket raised about it. */
export function useInquiry(id) {
  return useQuery({
    queryKey: ['inquiry', id],
    queryFn: async () => {
      const res = await api.get(`/api/inquiries/${id}/`)
      return res.data
    },
    enabled: Boolean(id),
  })
}
