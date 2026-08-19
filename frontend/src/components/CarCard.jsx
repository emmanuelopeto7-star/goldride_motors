import { Link } from 'react-router-dom'
import { formatPrice } from '../lib/format'
import { useFavourites } from '../hooks/useFavourites'

function CarCard({ car }) {
  const photoCount = car.images.length + (car.image ? 1 : 0)
  // Fall back to the gallery, the way the detail page does. A car can gain
  // photographs without one being promoted to the card - anything pushed to
  // stock, or uploaded from the dashboard - and rendering only car.image left
  // those showing an empty grey box in the grid while their own detail page
  // displayed the photo perfectly well.
  const cover = car.image || car.images[0]?.image
  const { isSaved, toggle } = useFavourites()
  const favourite = isSaved(car.id)

  return (
    <article className="group relative border border-line bg-surface transition-colors hover:border-line-hover">
      <div className="relative aspect-[4/3] overflow-hidden bg-page">
        {cover && (
          <img
            src={cover}
            alt={`${car.year} ${car.make} ${car.model}`}
            className="h-full w-full object-cover transition-transform duration-[400ms] group-hover:scale-[1.03]"
          />
        )}

        <span className="absolute left-3 top-3 rounded-full bg-surface px-3 py-1 text-badge uppercase">
          {car.availability}
        </span>

        {/* z-10 to sit above the stretched link below. */}
        <button
          type="button"
          onClick={() => toggle(car.id)}
          aria-pressed={favourite}
          aria-label={favourite ? 'Remove from saved' : 'Save this car'}
          className="absolute right-3 top-3 z-10 flex h-8 w-8 items-center justify-center rounded-full bg-surface"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M12 21s-7.5-4.7-9.3-9A5.3 5.3 0 0 1 12 6.6 5.3 5.3 0 0 1 21.3 12c-1.8 4.3-9.3 9-9.3 9z"
              fill={favourite ? 'currentColor' : 'none'}
              stroke="currentColor"
              strokeWidth="1.5"
            />
          </svg>
        </button>

        {photoCount > 0 && (
          <span className="absolute bottom-3 right-3 rounded-full bg-ink/70 px-3 py-1 text-badge text-surface">
            {photoCount}
          </span>
        )}
      </div>

      <div className="p-4">
        <div className="flex items-baseline justify-between gap-4">
          <p className="text-price font-semibold">{formatPrice(car.price)}</p>

          <Link
            to={`/cars/${car.id}#enquire`}
            className="relative z-10 flex shrink-0 items-center gap-2 text-meta"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
              <path
                d="M3 6h18v12H3z M3 6l9 7 9-7"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
              />
            </svg>
            Contact
          </Link>
        </div>

        {/* The stretched link: one real link for screen readers, whose ::after
            covers the whole card so the entire tile is clickable. */}
        <p className="mt-1 text-model text-ink-soft">
          <Link to={`/cars/${car.id}`} className="after:absolute after:inset-0">
            {car.year} {car.make} {car.model}
          </Link>
        </p>

        {car.location && (
          <p className="mt-1 text-meta text-ink-mute">{car.location}</p>
        )}
      </div>
    </article>
  )
}

export default CarCard
