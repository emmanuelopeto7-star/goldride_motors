import { useEffect, useRef } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import api from '../api/client'
import CarCard from '../components/CarCard'
import CardSkeleton from '../components/CardSkeleton'
import EmptyState from '../components/EmptyState'
import ErrorState from '../components/ErrorState'
import FilterBar from '../components/FilterBar'
import Hero from '../components/Hero'
import MakeGrid from '../components/MakeGrid'
import ModelCarousel from '../components/ModelCarousel'
import Page from '../components/Page'
import Pagination from '../components/Pagination'

const gridClass = 'grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3'

// Whitelisted rather than forwarding the whole query string - an unknown
// parameter should not reach the API, and page is handled separately.
const LIST_PARAMS = [
  'search',
  'make',
  'body_type',
  'fuel_type',
  'transmission',
  'ordering',
  'page',
]

function Home() {
  const [searchParams] = useSearchParams()
  const page = searchParams.get('page') ?? '1'

  const listRef = useRef(null)
  const openedAt = useRef(page)

  const params = {}
  LIST_PARAMS.forEach((key) => {
    const value = searchParams.get(key)
    if (value && !(key === 'page' && value === '1')) params[key] = value
  })

  const { data, isPending, isError, error, refetch } = useQuery({
    // The whole parameter set is this list's identity.
    queryKey: ['cars', params],
    queryFn: async () => {
      const res = await api.get('/api/cars/', { params })
      return res.data
    },
    // Hold the old results on screen while the next set loads, instead of
    // collapsing to skeletons and bouncing the layout on every click.
    placeholderData: keepPreviousData,
  })

  // Changing page should land on the cars, not send you back up past a
  // full-height hero you have already scrolled through. Compared by value
  // rather than by run count: StrictMode invokes effects twice, so a
  // "skip the first run" flag would fire on arrival instead.
  useEffect(() => {
    if (page !== openedAt.current) {
      listRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      openedAt.current = page
    }
  }, [page])

  const search = searchParams.get('search') ?? ''
  const make = searchParams.get('make') ?? ''
  const filtered = LIST_PARAMS.some(
    (key) => key !== 'page' && key !== 'ordering' && searchParams.get(key),
  )

  let label = 'cars available'
  if (search) label = `results for "${search}"`
  else if (filtered) label = 'matching cars'

  return (
    <>
      <Hero count={data?.count ?? 0} />

      <FilterBar />

      <Page>
        <div ref={listRef} className="scroll-mt-[200px]">
          {isPending && (
            <div className={gridClass}>
              {Array.from({ length: 6 }).map((_, index) => (
                <CardSkeleton key={index} />
              ))}
            </div>
          )}

          {/* DRF 404s a page past the last one, which a stale bookmark will
              hit. Retrying can never fix that; going back to page one can. */}
          {isError && error?.response?.status === 404 && (
            <EmptyState
              title="That page does not exist"
              message="There are fewer pages of results than that."
              action={
                <Link to="/" className="mt-8 inline-block text-meta text-ink underline">
                  Back to the first page
                </Link>
              }
            />
          )}

          {isError && error?.response?.status !== 404 && (
            <ErrorState
              message="We could not load the cars. Check your connection and try again."
              onRetry={refetch}
            />
          )}

          {data && data.count === 0 && (
            <EmptyState
              title={search || filtered ? 'No matches' : 'No cars listed yet'}
              message={
                search
                  ? `Nothing matched "${search}". Try a different make or model.`
                  : make
                    ? `We have no ${make} in stock right now.`
                    : filtered
                      ? 'Try widening your filters.'
                      : 'Check back soon.'
              }
              action={
                (search || filtered) && (
                  <Link to="/" className="mt-8 inline-block text-meta text-ink underline">
                    Clear all filters
                  </Link>
                )
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

              <Pagination
                count={data.count}
                hasNext={Boolean(data.next)}
                hasPrevious={Boolean(data.previous)}
              />
            </>
          )}
        </div>

        {/* Browse aids, not listings - they stay put while the grid filters. */}
        <MakeGrid />
        <ModelCarousel />
      </Page>
    </>
  )
}

export default Home
