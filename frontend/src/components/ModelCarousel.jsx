import { useRef } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import { counted } from '../lib/format'

/** §8.2 — 88px square thumb left, name, "N LISTINGS", chevron right.
 *  §8.3 — 40px bordered circle arrows, top-right of the section. */
function ModelCarousel() {
  const track = useRef(null)

  const { data: models } = useQuery({
    queryKey: ['models'],
    queryFn: async () => {
      const res = await api.get('/api/cars/models/')
      return res.data
    },
  })

  if (!models || models.length === 0) return null

  const top = models.slice(0, 12)

  function scrollBy(direction) {
    // One column-width of travel, whatever the viewport has made that.
    const width = track.current?.firstElementChild?.offsetWidth ?? 320
    track.current?.scrollBy({ left: direction * (width + 12), behavior: 'smooth' })
  }

  const arrow =
    'flex h-10 w-10 items-center justify-center rounded-full border border-line transition-colors hover:border-ink'

  return (
    <section className="mt-24">
      <div className="flex items-center justify-between gap-6">
        <h2 className="font-serif text-section">Popular models</h2>

        <div className="flex shrink-0 gap-3">
          <button type="button" onClick={() => scrollBy(-1)} aria-label="Previous" className={arrow}>
            <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M15 5l-7 7 7 7" stroke="currentColor" strokeWidth="1.5" fill="none" />
            </svg>
          </button>
          <button type="button" onClick={() => scrollBy(1)} aria-label="Next" className={arrow}>
            <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M9 5l7 7-7 7" stroke="currentColor" strokeWidth="1.5" fill="none" />
            </svg>
          </button>
        </div>
      </div>

      <div
        ref={track}
        className="mt-8 flex snap-x snap-mandatory gap-3 overflow-x-auto pb-2"
        style={{ scrollbarWidth: 'thin' }}
      >
        {top.map(({ make, model, count, image }) => (
          <Link
            key={`${make}-${model}`}
            to={`/?make=${encodeURIComponent(make)}&search=${encodeURIComponent(model)}`}
            className="flex w-[320px] shrink-0 snap-start items-center gap-4 border border-line bg-surface transition-colors hover:border-ink"
          >
            <div className="h-[88px] w-[88px] shrink-0 overflow-hidden bg-page">
              {image && (
                <img src={image} alt="" className="h-full w-full object-cover" />
              )}
            </div>

            <div className="min-w-0 flex-1 py-3">
              <p className="truncate text-model">
                {make} {model}
              </p>
              <p className="mt-1 text-badge uppercase text-ink-mute">
                {counted(count, 'listing')}
              </p>
            </div>

            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              aria-hidden="true"
              className="mr-4 shrink-0 text-ink-mute"
            >
              <path d="M9 5l7 7-7 7" stroke="currentColor" strokeWidth="1.5" fill="none" />
            </svg>
          </Link>
        ))}
      </div>
    </section>
  )
}

export default ModelCarousel
