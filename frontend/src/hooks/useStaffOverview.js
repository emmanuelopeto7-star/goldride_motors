import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'

/** The whole overview in one request.
 *
 *  Six requests would be six loading states on a screen whose entire job is to
 *  be read at a glance, and the figures would arrive out of step with each
 *  other - "collected" from one moment and "outstanding" from the next.
 *
 *  The window is in the URL rather than in component state, the same as every
 *  other staff screen: a manager who has switched to 24 months and wants to
 *  show somebody can send the address.
 */
export function useStaffOverview({ months = 12 } = {}) {
  const { isManager } = useAuth()

  return useQuery({
    queryKey: ['staff-overview', months],
    queryFn: async () => {
      const res = await api.get('/api/staff/overview/', { params: { months } })
      return res.data
    },
    enabled: isManager,
    // Sums over every payment and every listing. Fresh enough for a morning
    // read, and not something to re-run each time the tab regains focus.
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  })
}

export const WINDOWS = [
  [6, '6 months'],
  [12, '12 months'],
  [24, '24 months'],
]
