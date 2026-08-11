import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import CarCard from '../components/CarCard'
import CardSkeleton from '../components/CardSkeleton'
import EmptyState from '../components/EmptyState'
import ErrorState from '../components/ErrorState'
import Hero from '../components/Hero'
import Page from '../components/Page'

const gridClass = 'grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3'

function Home() {
  const [searchParams] = useSearchParams()
  const search = searchParams.get('search') ?? ''
  const make = searchParams.get('make') ?? ''

  const { data, isPending, isError, refetch } = useQuery({
    // Both filters are part of this list's identity, so both belong in the key.
    queryKey: ['cars', search, make],
    queryFn: async () => {
      const params = {}
      if (search) params.search = search
      if (make) params.make = make

      const res = await api.get('/api/cars/', { params })
      return res.data
    },
  })

  let label = 'cars available'
  if (search) label = `results for "${search}"`
  else if (make) label = make

  return (
    <>
      {/* Rendered unconditionally: the hero owns its own loading state, and
          the overlaid header needs something dark behind it either way. */}
      <Hero count={data?.count ?? 0} />

      <Page>
        {isPending && (
          <div className={gridClass}>
            {/* A fixed list that never reorders, so the index is a safe key. */}
            {Array.from({ length: 6 }).map((_, index) => (
              <CardSkeleton key={index} />
            ))}
          </div>
        )}

        {isError && (
          <ErrorState
            message="We could not load the cars. Check your connection and try again."
            onRetry={refetch}
          />
        )}

        {data && data.count === 0 && (
          <EmptyState
            title={search || make ? 'No matches' : 'No cars listed yet'}
            message={
              search
                ? `Nothing matched "${search}". Try a different make or model.`
                : make
                  ? `We have no ${make} in stock right now.`
                  : 'Check back soon.'
            }
          />
        )}

        {data && data.count > 0 && (
          <>
            <p className="text-badge uppercase text-ink-soft">
              {data.count} {label}
            </p>
            <div className={`mt-6 ${gridClass}`}>
              {data.results.map((car) => (
                <CarCard key={car.id} car={car} />
              ))}
            </div>
          </>
        )}
      </Page>
    </>
  )
}

export default Home
