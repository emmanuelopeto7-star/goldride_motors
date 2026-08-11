import { useEffect, useState } from 'react'

export function useMediaQuery(query) {
  // Lazy initialiser: runs once on mount, not on every render.
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches)

  useEffect(() => {
    const list = window.matchMedia(query)
    const onChange = (event) => setMatches(event.matches)

    setMatches(list.matches)
    list.addEventListener('change', onChange)

    return () => list.removeEventListener('change', onChange)
  }, [query])

  return matches
}
