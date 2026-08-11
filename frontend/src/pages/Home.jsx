import { useEffect, useRef } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import api from '../api/client'
import CarCard from '../components/CarCard'
import CardSkeleton from '../components/CardSkeleton'
import EmptyState from '../components/EmptyState'
import ErrorState from '../components/ErrorState'
import Hero from '../components/Hero'
import Page from '../components/Page'
import Pagination from '../components/Pagination'

const gridClass = 'grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3'

function Home() {
  const [searchParams] = useSearchParams()
  const search = searchParams.get('search') ?? ''
  const make = searchParams.get('make') ?? ''
  const page = searchParams.get('page') ?? '1'

  const listRef = useRef(null)
  const firstRender = useRef(true)

  const { data, isPending, isError, error, refetch } = useQuery({
    // Every input that changes what this list contains belongs in the key.
    queryKey: ['cars', search, make, page],
    queryFn: async () => {
      const params = {}
      if (search) params.search = search
      if (make) params.make = make
      if (page !== '1') params.page = page

      const res = await api.get('/api/cars/', { params })
      return res.data
    },
    // Hold the old page on screen while the next one loads, instead of
    // collapsing to skeletons and bouncing the layout on every click.
    placeholderData: keepPreviousData,
  })

  // Changing page should land on the cars, not send you back up past a
  // full-height hero you have already scrolled through.
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false
      return
    }
    listRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [page])

  let label = 'cars available'
  if (search) label = `results for "${search}"`
  else if (make) label = make

  return (
    <>
      <Hero count={data?.count ?? 0} />

      <Page>
        <div ref={listRef} className="scroll-mt-32">
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
              message={`There are only ${Math.ceil((data?.count ?? 0) / 12) || 1} pages of results.`}
              action={
                <Link
                  to="/"
                  className="mt-8 inline-block text-meta text-ink underline"
                >
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

              <Pagination
                count={data.count}
                hasNext={Boolean(data.next)}
                hasPrevious={Boolean(data.previous)}
              />
            </>
          )}
        </div>
      </Page>
    </>
  )
}

export default Home
