import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import { formatPrice } from '../lib/format'
import Gallery from '../components/Gallery'
import EnquiryPanel from '../components/EnquiryPanel'
import ErrorState from '../components/ErrorState'
import Page from '../components/Page'

const numberFormat = new Intl.NumberFormat('en-KE')

function CarDetail() {
  const { id } = useParams()
  const [expanded, setExpanded] = useState(false)

  const { data: car, isPending, isError, error, refetch } = useQuery({
    queryKey: ['car', id],
    queryFn: async () => {
      const res = await api.get(`/api/cars/${id}/`)
      return res.data
    },
  })

  if (isPending) {
    return (
      <Page>
        <div className="h-[320px] w-full animate-pulse bg-line lg:h-[520px]" />
        <div className="mt-8 h-12 w-96 animate-pulse bg-line" />
        <div className="mt-12 h-64 w-full max-w-[560px] animate-pulse bg-line" />
      </Page>
    )
  }

  if (isError) {
    // A missing car stays missing, so no retry button on a 404.
    const missing = error?.response?.status === 404
    return (
      <Page>
        <ErrorState
          title={missing ? 'Car not found' : 'Something went wrong'}
          message={
            missing
              ? 'This listing may have been sold or removed.'
              : 'We could not load this listing.'
          }
          onRetry={missing ? undefined : refetch}
        />
      </Page>
    )
  }

  const photos = [car.image, ...car.images.map((item) => item.image)].filter(Boolean)
  const title = `${car.year} ${car.make} ${car.model}`
  const km = (value) => `${numberFormat.format(value)} km`
  const cc = (value) => `${numberFormat.format(value)} cc`

  // Anything unknown is dropped rather than shown blank.
  const stats = [
    { label: 'Year', value: car.year },
    { label: 'Mileage', value: car.mileage_km && km(car.mileage_km) },
    { label: 'Engine', value: car.engine_cc && cc(car.engine_cc) },
    { label: 'Fuel type', value: car.fuel_type_label },
    { label: 'Transmission', value: car.transmission_label },
  ].filter((stat) => stat.value)

  const details = [
    { label: 'Location', value: car.location },
    { label: 'Mileage', value: car.mileage_km && km(car.mileage_km) },
    { label: 'Engine', value: car.engine_cc && cc(car.engine_cc) },
    { label: 'Car type', value: car.body_type_label },
    { label: 'Drive train', value: car.drivetrain_label },
    { label: 'Transmission', value: car.transmission_label },
    { label: 'Fuel type', value: car.fuel_type_label },
    { label: 'Condition', value: car.condition },
    { label: 'Colour', value: car.exterior_colour },
    { label: 'Interior colour', value: car.interior_colour },
    { label: 'VIN', value: car.vin },
    { label: 'Reference', value: car.reference },
  ].filter((row) => row.value)

  const isLong = car.description.length > 320
  const shown = isLong && !expanded ? `${car.description.slice(0, 320)}…` : car.description

  return (
    <div className="mx-auto max-w-[1440px] px-5 py-8 lg:px-12 lg:py-12">
      <nav className="mb-6 flex items-center gap-2 text-meta text-ink-soft">
        <Link to="/" className="hover:text-ink">
          Cars
        </Link>
        <span aria-hidden="true">/</span>
        <Link to={`/?make=${encodeURIComponent(car.make)}`} className="hover:text-ink">
          {car.make}
        </Link>
        <span aria-hidden="true">/</span>
        <span className="text-ink">{car.model}</span>
      </nav>

      <Gallery photos={photos} title={title} />

      <div className="mt-8 flex flex-wrap items-end justify-between gap-x-16 gap-y-4 border-b border-line pb-8">
        <div className="max-w-[640px]">
          <span className="text-badge uppercase text-ink-soft">{car.availability}</span>
          <h1 className="mt-2 font-serif text-h1">{title}</h1>
        </div>
        <p className="font-serif text-h1">{formatPrice(car.price)}</p>
      </div>

      <div className="mt-12 grid gap-16 lg:grid-cols-[1fr_380px]">
        <div>
          {/* One lonely figure reads as broken, so the strip needs at least two. */}
          {stats.length > 1 && (
            <dl className="flex flex-wrap gap-x-16 gap-y-8 border-b border-line pb-8">
              {stats.map((stat) => (
                <div key={stat.label}>
                  <dd className="text-price">{stat.value}</dd>
                  <dt className="mt-1 text-meta text-ink-soft">{stat.label}</dt>
                </div>
              ))}
            </dl>
          )}

          <section className="mt-12">
            <h2 className="font-serif text-section">About This Car</h2>
            <p className="mt-4 max-w-[68ch] whitespace-pre-line text-model leading-relaxed text-ink-soft">
              {shown}
            </p>
            {isLong && (
              <button
                type="button"
                onClick={() => setExpanded(!expanded)}
                className="mt-3 text-model text-ink underline"
              >
                {expanded ? 'view less' : 'view more'}
              </button>
            )}
          </section>

          {details.length > 0 && (
            <section className="mt-12">
              <h2 className="font-serif text-section">Car Details</h2>
              <dl className="mt-4 max-w-[560px]">
                {details.map((row) => (
                  <div
                    key={row.label}
                    className="flex justify-between gap-8 border-b border-line py-3 text-meta"
                  >
                    <dt className="text-ink-soft">{row.label}</dt>
                    <dd className="text-right capitalize">{row.value}</dd>
                  </div>
                ))}
              </dl>
            </section>
          )}
        </div>

        <EnquiryPanel car={car} title={title} />
      </div>
    </div>
  )
}

export default CarDetail
