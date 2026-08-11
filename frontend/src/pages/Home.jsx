import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import CarCard from '../components/CarCard'
import Hero from '../components/Hero'

function Home() {
  const [searchParams] = useSearchParams()
  const search = searchParams.get('search') ?? ''
  const make = searchParams.get('make') ?? ''

  const { data, isPending, isError } = useQuery({
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

  if (isPending) return <p>Loading...</p>
  if (isError) return <p>Unable to load cars.</p>

  let label = 'cars available'
  if (search) label = `results for "${search}"`
  else if (make) label = make

  return (
    <>
      <Hero count={data.count} />

      <div className="mx-auto max-w-[1440px] px-5 py-16 lg:px-12">
        <p className="text-badge uppercase text-ink-soft">
          {data.count} {label}
        </p>
        <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          {data.results.map((car) => (
            <CarCard key={car.id} car={car} />
          ))}
        </div>
      </div>
    </>
  )
}

export default Home
