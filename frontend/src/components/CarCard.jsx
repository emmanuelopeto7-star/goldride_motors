import {formatPrice} from '../lib/format.js'
import { Link } from 'react-router-dom'

function CarCard({ car }) {
    const photoCount = car.images.length + (car.image ? 1 : 0)

    return(
        <Link to={`/cars/${car.id}`} className="block">
        <article className="group border border-line bg-surface transition-colors hover:border-line-hover">
      <div className="relative aspect-[4/3] overflow-hidden bg-page">
        {car.image && (
          <img
            src={car.image}
            alt={`${car.year} ${car.make} ${car.model}`}
            className="h-full w-full object-cover transition-transform duration-[400ms] group-hover:scale-[1.03]"
          />
        )}
        <span className="absolute left-3 top-3 rounded-full bg-surface px-3 py-1 text-badge uppercase">
          {car.availability}
        </span>
        {photoCount > 0 && (
          <span className="absolute bottom-3 right-3 rounded-full bg-ink/70 px-3 py-1 text-badge text-surface">
            {photoCount}
          </span>
        )}

         </div>
      <div className="p-4">
        <p className="text-price font-semibold">{formatPrice(car.price)}</p>
        <p className="text-model text-ink-soft">
          {car.year} {car.make} {car.model}
        </p>
      </div>
    </article>
    </Link>
  )
}

export default CarCard
