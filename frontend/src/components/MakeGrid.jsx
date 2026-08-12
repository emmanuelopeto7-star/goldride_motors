import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'

/** §8.1 — 1:1 bordered tiles, 8 / 4 / 3 across. The rule asks for a
 *  manufacturer logo at 60% width; we have none, so the tile carries the make
 *  set in the display serif instead. Swap in logos when there are files. */
function MakeGrid() {
  const { data: makes } = useQuery({
    queryKey: ['makes'],
    queryFn: async () => {
      const res = await api.get('/api/cars/makes/')
      return res.data
    },
  })

  if (!makes || makes.length === 0) return null

  return (
    <section className="mt-24">
      <h2 className="font-serif text-section">Browse by make</h2>

      <div className="mt-8 grid grid-cols-3 gap-3 md:grid-cols-4 lg:grid-cols-8">
        {makes.map(({ make, count }) => (
          <Link
            key={make}
            to={`/?make=${encodeURIComponent(make)}`}
            className="flex aspect-square flex-col items-center justify-center border border-line bg-surface p-3 text-center transition-colors hover:border-ink"
          >
            <span className="font-serif text-[15px] leading-tight">{make}</span>
            <span className="mt-1 text-badge uppercase text-ink-mute">
              {count}
            </span>
          </Link>
        ))}
      </div>
    </section>
  )
}

export default MakeGrid
