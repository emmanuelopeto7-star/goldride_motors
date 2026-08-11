import { useState } from 'react'
import Modal from './Modal'

/** The mosaic: one large frame left, a 2x2 grid right, the rest behind the
 *  photo-count button. The row height is fixed rather than derived from
 *  aspect ratios, so a missing tile or an odd-shaped photo cannot make one
 *  column four times the height of the other. */
function Gallery({ photos, title }) {
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)

  if (photos.length === 0) {
    return <div className="h-[320px] w-full border border-line bg-page lg:h-[520px]" />
  }

  const [lead, ...rest] = photos
  const tiles = rest.slice(0, 4)

  function openAt(index) {
    setActiveIndex(index)
    setOpen(true)
  }

  return (
    <>
      <div className="relative grid h-[320px] gap-3 lg:h-[520px] lg:grid-cols-2">
        <button
          type="button"
          onClick={() => openAt(0)}
          className="h-full overflow-hidden border border-line"
        >
          <img
            src={lead}
            alt={title}
            className="h-full w-full object-cover transition-transform duration-[400ms] hover:scale-[1.03]"
          />
        </button>

        {tiles.length > 0 && (
          <div className="hidden h-full grid-cols-2 grid-rows-2 gap-3 lg:grid">
            {tiles.map((src, index) => (
              <button
                key={src}
                type="button"
                onClick={() => openAt(index + 1)}
                className="h-full overflow-hidden border border-line"
              >
                <img
                  src={src}
                  alt=""
                  className="h-full w-full object-cover transition-transform duration-[400ms] hover:scale-[1.03]"
                />
              </button>
            ))}
          </div>
        )}

        <button
          type="button"
          onClick={() => openAt(0)}
          className="absolute bottom-4 right-4 rounded-full bg-ink/70 px-4 py-2 text-badge uppercase text-surface"
        >
          {photos.length} photos
        </button>
      </div>

      {open && (
        <Modal onClose={() => setOpen(false)}>
          <div className="h-[60vh] overflow-hidden bg-page">
            <img
              src={photos[activeIndex]}
              alt={title}
              className="h-full w-full object-contain"
            />
          </div>

          <div
            className="mt-3 flex gap-3 overflow-x-auto pb-2"
            style={{ scrollbarWidth: 'thin' }}
          >
            {photos.map((src, index) => (
              <button
                key={src}
                type="button"
                aria-label={`Photo ${index + 1} of ${photos.length}`}
                onClick={() => setActiveIndex(index)}
                className={`h-20 w-20 shrink-0 overflow-hidden border ${
                  index === activeIndex ? 'border-ink' : 'border-line'
                }`}
              >
                <img src={src} alt="" className="h-full w-full object-cover" />
              </button>
            ))}
          </div>

          <p className="mt-3 text-center text-meta text-ink-soft">
            {activeIndex + 1} / {photos.length}
          </p>
        </Modal>
      )}
    </>
  )
}

export default Gallery
