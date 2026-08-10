import { useQuery } from '@tanstack/react-query';
import api from './api/client';
import CarCard from './components/CarCard'

function App() {
  const { data, isPending, isError } = useQuery({
    queryKey: ['cars'],
    queryFn: async () => {
      const res = await api.get('/api/cars/')
      return res.data
    },
  })

if (isPending) return <p className="p-12">Loading…</p>
if (isError) return <p className="p-12">Error loading cars.</p>

return (
  <div className="min-h-screen bg-page text-ink p-12">
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

export default App