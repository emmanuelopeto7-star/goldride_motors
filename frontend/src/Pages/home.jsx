import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import CarCard from '../components/CarCard'

function Home() {
     const { data, isPending, isError } = useQuery({
    queryKey: ['cars'],
    queryFn: async () => {
      const res = await api.get('/api/cars/')
      return res.data
    },
  })

  if (isPending) return <p>Loading...</p>
  if (isError) return <p>Unable to load cars.</p>

 
  return (
    <div className="mx-auto max-w-[1440px] px-5 py-16 lg:px-12">
      <p className="text-badge uppercase text-ink-soft">
        {data.count} cars available
      </p>
      <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
        {data.results.map((car) => (
          <CarCard key={car.id} car={car} />
        ))}
      </div>
    </div>
  )
}

export default Home

