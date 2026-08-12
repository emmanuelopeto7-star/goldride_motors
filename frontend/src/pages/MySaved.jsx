import { Link } from 'react-router-dom'
import CarCard from '../components/CarCard'
import CardSkeleton from '../components/CardSkeleton'
import EmptyState from '../components/EmptyState'
import { useFavourites } from '../hooks/useFavourites'

function MySaved() {
  const { cars, isPending } = useFavourites()

  if (isPending) {
    return (
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <CardSkeleton key={index} />
        ))}
      </div>
    )
  }

  if (cars.length === 0) {
    return (
      <EmptyState
        title="Nothing saved yet"
        message="Tap the heart on any car and it will be kept here."
        action={
          <Link to="/" className="mt-8 inline-block text-meta text-ink underline">
            Browse cars
          </Link>
        }
      />
    )
  }

  return (
    <>
      <p className="text-badge uppercase text-ink-soft">
        {cars.length} saved {cars.length === 1 ? 'car' : 'cars'}
      </p>
      <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
        {cars.map((car) => (
          <CarCard key={car.id} car={car} />
        ))}
      </div>
    </>
  )
}

export default MySaved
