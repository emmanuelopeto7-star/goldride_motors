import { useEffect, useState } from 'react'

/** True once the page has moved past `threshold` pixels (DESIGN.md §4.5). */
export function useScrolled(threshold = 80) {
  const [scrolled, setScrolled] = useState(() => window.scrollY > threshold)

  useEffect(() => {
    function onScroll() {
      setScrolled(window.scrollY > threshold)
    }

    // Read once on mount: a reload halfway down a page must not start overlaid.
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })

    return () => window.removeEventListener('scroll', onScroll)
  }, [threshold])

  return scrolled
}
