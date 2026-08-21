import { useRef } from 'react'
import Modal from './Modal'
import { useCarImages } from '../hooks/useCarImages'

/** Photographs for one listing.
 *
 *  This is the screen that unblocks the catalogue: most cars have no picture
 *  and until now the only way to add one was the Django admin, one row at a
 *  time. Multi-select upload, because a car arrives with a dozen shots.
 */
function CarPhotosModal({ car, onClose }) {
  const fileInput = useRef(null)
  const { query, upload, remove, setMain, canDelete } = useCarImages(car.id)

  const images = query.data ?? []
  const result = upload.data

  function handleFiles(event) {
    const files = [...event.target.files]
    if (files.length) upload.mutate(files)
    // Clear it, or picking the same file twice in a row does nothing.
    event.target.value = ''
  }

  return (
    <Modal onClose={onClose}>
      <h2 className="text-center font-serif text-section">Photographs</h2>
      <p className="mt-2 text-center text-meta text-ink-soft">
        {car.year} {car.make} {car.model}
      </p>

      <div className="mt-8">
        <input
          ref={fileInput}
          type="file"
          accept="image/*"
          multiple
          onChange={handleFiles}
          className="hidden"
        />
        <button
          type="button"
          disabled={upload.isPending}
          onClick={() => fileInput.current?.click()}
          className="h-12 w-full bg-ink text-badge uppercase text-surface disabled:opacity-50"
        >
          {upload.isPending ? 'Uploading...' : 'Add photographs'}
        </button>
        <p className="mt-2 text-meta text-ink-mute">
          Pick several at once. Landscape 4:3 matches the card crop.
        </p>
      </div>

      {/* Reported per file: one photo being rejected should not read as the
          whole upload having failed. */}
      {result?.failed?.length > 0 && (
        <ul className="mt-4">
          {result.failed.map((message) => (
            <li key={message} className="text-meta text-ink">
              {message}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-8 border-t border-line pt-6">
        {query.isPending ? (
          <div className="h-24 w-full animate-pulse bg-line" />
        ) : images.length === 0 ? (
          <p className="text-meta text-ink-soft">
            No photographs yet. This listing shows a blank card on the site.
          </p>
        ) : (
          <>
            <p className="text-badge uppercase text-ink-soft">
              {images.length} on file
            </p>
            <ul className="mt-4 grid grid-cols-3 gap-3">
              {images.map((image) => (
                <li key={image.id} className="border border-line">
                  <img
                    src={image.image}
                    alt=""
                    loading="lazy"
                    className="aspect-[4/3] w-full object-cover"
                  />
                  <div className="flex items-center justify-between gap-2 p-2">
                    <button
                      type="button"
                      disabled={setMain.isPending}
                      onClick={() => setMain.mutate({ url: image.image })}
                      className="text-meta text-ink underline disabled:opacity-50"
                    >
                      Main
                    </button>
                    {/* Only a Manager may delete - the API refuses Sales, so
                        offering the control would be a promise it breaks. */}
                    {canDelete && (
                      <button
                        type="button"
                        disabled={remove.isPending}
                        onClick={() => remove.mutate(image.id)}
                        className="text-meta text-ink-soft underline disabled:opacity-50"
                      >
                        Remove
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>

      <button
        type="button"
        onClick={onClose}
        className="mt-8 h-12 w-full border border-ink text-badge uppercase"
      >
        Done
      </button>
    </Modal>
  )
}

export default CarPhotosModal
