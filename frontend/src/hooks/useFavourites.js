import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'

const KEY = 'goldride_favourites'

function readLocal() {
  try {
    const raw = localStorage.getItem(KEY)
    return new Set(raw ? JSON.parse(raw) : [])
  } catch {
    // Corrupt or unavailable storage must not take the listing page down.
    return new Set()
  }
}

/** Saved cars. Signed in they live on the account; signed out they live in
 *  this browser and are pushed up the first time you sign in, so hearting
 *  something before you have an account is never wasted. */
export function useFavourites() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const merged = useRef(false)

  // localStorage is not reactive, so the signed-out set needs a state mirror
  // or the heart never repaints.
  const [localIds, setLocalIds] = useState(readLocal)

  const query = useQuery({
    queryKey: ['favourites'],
    queryFn: async () => {
      const res = await api.get('/api/favourites/')
      return res.data.results ?? res.data
    },
    enabled: Boolean(user),
  })

  const remote = query.data
  const ids = user ? new Set((remote ?? []).map((item) => item.car)) : localIds

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['favourites'] })

  const add = useMutation({
    mutationFn: (carId) => api.post('/api/favourites/', { car: carId }),
    onSuccess: invalidate,
  })

  const remove = useMutation({
    mutationFn: (carId) => api.delete(`/api/favourites/${carId}/`),
    onSuccess: invalidate,
  })

  // Push anything hearted before signing in, once, then forget it locally.
  useEffect(() => {
    if (!user || merged.current || !remote) return
    merged.current = true

    const local = readLocal()
    if (local.size === 0) return

    Promise.allSettled(
      [...local].map((carId) => api.post('/api/favourites/', { car: carId })),
    ).then(() => {
      localStorage.removeItem(KEY)
      setLocalIds(new Set())
      invalidate()
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, remote])

  function toggle(carId) {
    if (user) {
      if (ids.has(carId)) remove.mutate(carId)
      else add.mutate(carId)
      return
    }

    const next = readLocal()
    if (next.has(carId)) next.delete(carId)
    else next.add(carId)

    localStorage.setItem(KEY, JSON.stringify([...next]))
    setLocalIds(next)
  }

  return {
    ids,
    cars: (remote ?? []).map((item) => item.car_detail),
    isPending: Boolean(user) && query.isPending,
    isSaved: (carId) => ids.has(carId),
    toggle,
  }
}
