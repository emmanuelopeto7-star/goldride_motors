import { useQuery } from '@tanstack/react-query'
import api from '../api/client'

/** Shared by Hero and Layout. Same query key, so react-query serves both from
 *  one cache entry and one request - the header needs to know whether a hero
 *  will draw before it decides to go transparent. */
export function useHeroBanner() {
  return useQuery({
    queryKey: ['hero'],
    queryFn: async () => {
      const res = await api.get('/api/hero/')
      // No active banner comes back as an empty body, not as null.
      return res.data || null
    },
  })
}
