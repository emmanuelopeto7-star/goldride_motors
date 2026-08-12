import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import api from '../api/client'

/** DESIGN.md §4.3 - the row of makes under the search bar. */
function BrandStrip({ overlay }) {
  const [searchParams] = useSearchParams()
  const activeMake = searchParams.get('make') ?? ''
  const track = useRef(null)

  // A vertical wheel does nothing over a horizontal scroller, and the bar is
  // hidden, so a mouse user has no way to reach makes past the edge. Bound as
  // a native listener because it must be non-passive to preventDefault.
  useEffect(() => {
    const el = track.current
    if (!el) return

    function onWheel(event) {
      if (el.scrollWidth <= el.clientWidth) return
      // Leave genuine horizontal gestures - trackpads - alone.
      if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return

      event.preventDefault()
      el.scrollLeft += event.deltaY
    }

    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  })

  const { data: makes } = useQuery({
    queryKey: ['makes'],
    queryFn: async () => {
      const res = await api.get('/api/cars/makes/')
      return res.data
    },
  })

  if (!makes || makes.length === 0) return null

  return (
    <div className={overlay ? '' : 'border-t border-line'}>
      {/* Matches row 1: full width so the strip lines up with the nav above. */}
      <div className="w-full px-5 lg:px-12">
        <nav
          ref={track}
          className="flex h-12 items-center gap-6 overflow-x-auto whitespace-nowrap"
          style={{
            // Fading edges, so a scrolled-off make bleeds out rather than
            // being chopped. A mask, not a background - §2.2 stands.
            maskImage:
              'linear-gradient(to right, transparent, black 24px, black calc(100% - 24px), transparent)',
            scrollbarWidth: 'none',
          }}
        >
          {makes.map(({ make, count }) => {
            const isActive = make.toLowerCase() === activeMake.toLowerCase()

            return (
              <Link
                key={make}
                to={`/?make=${encodeURIComponent(make)}`}
                title={`${count} listed`}
                className={`shrink-0 text-[14px] transition-colors duration-200 ${
                  overlay ? 'text-surface' : 'text-ink'
                } ${isActive ? 'underline underline-offset-4' : 'no-underline'}`}
              >
                {make}
              </Link>
            )
          })}
        </nav>
      </div>
    </div>
  )
}

export default BrandStrip
