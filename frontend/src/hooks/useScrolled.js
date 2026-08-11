import { useEffect, useState } from 'react'

/** True once the page has moved further than `threshold` pixels down. */
export function useScrolled(threshold = 80) {
  const [scrolled, setScrolled] = useState(() => window.scrollY > threshold)

  useEffect(() => {
    function onScroll() {
      setScrolled(window.scrollY > threshold)
    }

    // Run once: a reload part-way down the page must not start in overlay mode.
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })

    return () => window.removeEventListener('scroll', onScroll)
  }, [threshold])

  return scrolled
}
