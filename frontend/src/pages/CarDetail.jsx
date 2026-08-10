import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import { formatPrice } from '../lib/format'

function CarDetail() {
  const { id } = useParams()
  const [activeIndex, setActiveIndex] = useState(0)

  const { data: car, isPending, isError } = useQuery({
    queryKey: ['car', id],
    queryFn: async () => {
      const res = await api.get(`/api/cars/${id}/`)
      return res.data
    },
  })

  if (isPending) return <p className="p-12">Loading…</p>
  if (isError) return <p className="p-12">Car not found.</p>

  const photos = [car.image, ...car.images.map((item) => item.image)].filter(Boolean)
  const title = `${car.year} ${car.make} ${car.model}`

  return (
    <div className="mx-auto max-w-[1440px] px-5 py-16 lg:px-12">
      <div className="grid gap-12 lg:grid-cols-[3fr_2fr]">
        <div>
          <div className="aspect-[4/3] overflow-hidden border border-line bg-surface">
            {photos.length > 0 && (
              <img
                src={photos[activeIndex]}
                alt={title}
                className="h-full w-full object-cover"
              />
            )}
          </div>

          {photos.length > 1 && (
            <div className="mt-3 flex flex-wrap gap-3">
              {photos.map((src, index) => (
                <button
                  key={src}
                  type="button"
                  onClick={() => setActiveIndex(index)}
                  className={`h-24 w-24 overflow-hidden border ${
                    index === activeIndex ? 'border-ink' : 'border-line'
                  }`}
                >
                  <img src={src} alt="" className="h-full w-full object-cover" />
                </button>
              ))}
            </div>
          )}
        </div>

        <div>
          <span className="inline-block rounded-full border border-line px-3 py-1 text-badge uppercase">
            {car.availability}
          </span>

          <h1 className="mt-4 font-serif text-h1">{title}</h1>
          <p className="mt-4 text-price font-semibold">{formatPrice(car.price)}</p>

          <dl className="mt-8 border-t border-line text-meta">
            <div className="flex justify-between border-b border-line py-3">
              <dt className="text-ink-soft">Condition</dt>
              <dd className="uppercase">{car.condition}</dd>
            </div>
            <div className="flex justify-between border-b border-line py-3">
              <dt className="text-ink-soft">Year</dt>
              <dd>{car.year}</dd>
            </div>
            <div className="flex justify-between border-b border-line py-3">
              <dt className="text-ink-soft">Make</dt>
              <dd>{car.make}</dd>
            </div>
          </dl>

          <p className="mt-8 text-model text-ink-soft">{car.description}</p>

          <button
            type="button"
            className="mt-8 h-12 w-full bg-ink text-badge uppercase text-surface"
          >
            Enquire about this car
          </button>
        </div>
      </div>
    </div>
  )
}

export default CarDetail