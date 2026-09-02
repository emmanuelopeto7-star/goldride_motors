import { useState } from 'react'
import api from '../api/client'
import { counted, formatPrice } from '../lib/format'
import Button from './Button'

/** What a dealership applied with, as staff see it before deciding.
 *
 *  This is the evidence for a decision that lists a car the moment it is made,
 *  so it shows the photographs a buyer would see and the paperwork that says
 *  the car is theirs to sell.
 *
 *  Paperwork is fetched, never linked. The download endpoint checks who is
 *  asking, which an <a href> cannot carry a token to - and a logbook sitting
 *  in a plain URL is a logbook in a browser history and a proxy log.
 */

function useDownload() {
  const [failed, setFailed] = useState(null)

  async function download(document_) {
    setFailed(null)
    try {
      const res = await api.get(`/api/staff/dealers/documents/${document_.id}/`, {
        responseType: 'blob',
      })
      const url = URL.createObjectURL(res.data)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = document_.filename
      anchor.click()
      // Revoked once the click has been handed to the browser; leaving these
      // around keeps the whole file alive in memory for the life of the tab.
      URL.revokeObjectURL(url)
    } catch {
      setFailed(document_.id)
    }
  }

  return { download, failed }
}

function readableSize(bytes) {
  if (!bytes && bytes !== 0) return ''
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
  return `${Math.max(1, Math.round(bytes / 1024))}KB`
}

function ApplicationCar({ cars = [], documents = [] }) {
  const { download, failed } = useDownload()

  if (cars.length === 0 && documents.length === 0) {
    return (
      <p className="text-meta text-ink-mute">
        This application arrived before we asked for a car.
      </p>
    )
  }

  return (
    <div className="space-y-8">
      {cars.map((car) => (
        <div key={car.id}>
          <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
            <p className="text-model">
              {car.year} {car.make} {car.model}
            </p>
            <p className="text-price">{formatPrice(car.price)}</p>
          </div>

          <p className="mt-1 text-meta text-ink-soft">
            {car.mileage_km
              ? `${car.mileage_km.toLocaleString('en-KE')} km · `
              : ''}
            {car.exterior_colour ? `${car.exterior_colour} · ` : ''}
            {counted(car.images.length, 'photograph')}
          </p>

          {car.images.length > 0 ? (
            <ul className="mt-4 flex flex-wrap gap-3">
              {car.images.map((image) => (
                <li key={image.id}>
                  <img
                    src={image.image}
                    alt=""
                    loading="eager"
                    className="h-24 w-32 border border-line object-cover"
                  />
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-4 text-meta text-ink-mute">
              No photographs. Approving lists it without one.
            </p>
          )}

          {car.description && (
            <p className="mt-4 max-w-[560px] text-meta text-ink-soft">
              {car.description}
            </p>
          )}

          {car.published_car_id && (
            <p className="mt-4 text-meta text-ink-soft">
              Listed as car #{car.published_car_id}.
            </p>
          )}
        </div>
      ))}

      {documents.length > 0 && (
        <div className="border-t border-line pt-6">
          <p className="text-badge uppercase text-ink-soft">Paperwork</p>
          <p className="mt-2 text-meta text-ink-mute">
            Staff only. These are never shown on the site.
          </p>

          <ul className="mt-4 space-y-3">
            {documents.map((document_) => (
              <li
                key={document_.id}
                className="flex flex-wrap items-center gap-4 border border-line p-3"
              >
                <span className="text-meta">{document_.kind_label}</span>
                <span className="min-w-0 flex-1 truncate text-meta text-ink-soft">
                  {document_.filename}
                  {document_.size ? ` · ${readableSize(document_.size)}` : ''}
                </span>
                <Button
                  variant="quiet"
                  onClick={() => download(document_)}
                >
                  Download
                </Button>
                {failed === document_.id && (
                  <span className="w-full text-meta text-ink">
                    That file could not be fetched.
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export default ApplicationCar
