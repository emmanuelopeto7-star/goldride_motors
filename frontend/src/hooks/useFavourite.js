import { useState } from 'react'

const KEY = 'goldride_favourites'

function read() {
  try {
    const raw = localStorage.getItem(KEY)
    return new Set(raw ? JSON.parse(raw) : [])
  } catch {
    // Corrupt or unavailable storage must not take the listing page down.
    return new Set()
  }
}

function write(set) {
  localStorage.setItem(KEY, JSON.stringify([...set]))
}

/** Device-local favourites. Survives a refresh, not a change of browser -
 *  syncing across devices needs somewhere on the server to put them. */
export function useFavourite(carId) {
  const [favourite, setFavourite] = useState(() => read().has(carId))

  function toggle() {
    const set = read()
    if (set.has(carId)) set.delete(carId)
    else set.add(carId)

    write(set)
    setFavourite(set.has(carId))
  }

  return [favourite, toggle]
}
