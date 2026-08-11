import { Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'

// §4.3 asks for fading edges so the row reads as scrollable rather than clipped.
const fade =
  'linear-gradient(to right, transparent 0, #000 24px, #000 calc(100% - 24px), transparent 100%)'

function BrandStrip({ overlay }) {
  const [searchParams] = useSearchParams()
  const activeMake = searchParams.get('make') ?? ''

  const { data: makes } = useQuery({
    queryKey: ['makes'],
    queryFn: async () => {
      const res = await api.get('/api/cars/makes/')
      return res.data
    },
  })

  if (!makes || makes.length === 0) return null

  return (
    <nav
      aria-label="Browse by make"
      className="overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      style={{ maskImage: fade, WebkitMaskImage: fade }}
    >
      <ul className="mx-auto flex h-12 max-w-[1440px] items-center gap-6 px-5 lg:px-12">
        {makes.map(({ make }) => (
          <li key={make} className="shrink-0">
            <Link
              to={`/?make=${encodeURIComponent(make)}`}
              className={`whitespace-nowrap text-[14px] transition-colors duration-200 ${
                overlay ? 'text-surface' : 'text-ink'
              } ${make === activeMake ? 'underline underline-offset-4' : ''}`}
            >
              {make}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  )
}

export default BrandStrip
