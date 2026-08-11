import { useCallback, useEffect, useState } from 'react'
import Modal from './Modal'

/** The mosaic: one large frame left, a 2x2 grid right, the rest behind the
 *  photo-count button. The row height is fixed rather than derived from
 *  aspect ratios, so an odd-shaped photo cannot make one column four times
 *  the height of the other. */
function Gallery({ photos, title }) {
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)

  const count = photos.length

  const step = useCallback(
    (delta) => setActiveIndex((index) => (index + delta + count) % count),
    [count],
  )

  // Arrow keys are expected in a viewer. Escape is handled by Modal.
  useEffect(() => {
    if (!open) return

    function onKey(event) {
      if (event.key === 'ArrowRight') step(1)
      if (event.key === 'ArrowLeft') step(-1)
    }

    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, step])

  // Every hook above this line, so the early return cannot change how many run.
  if (count === 0) {
    return <div className="h-[320px] w-full border border-line bg-page lg:h-[520px]" />
  }

  const [lead, ...rest] = photos
  const tiles = rest.slice(0, 4)

  function openAt(index) {
    setActiveIndex(index)
    setOpen(true)
  }

  const arrow =
    'absolute top-1/2 z-10 flex h-12 w-12 -translate-y-1/2 items-center justify-center rounded-full border border-white/30 text-surface'

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
          {count} photos
        </button>
      </div>

      {open && (
        <Modal onClose={() => setOpen(false)} size="full">
          <div className="flex h-full flex-col px-4 py-16 lg:px-16 lg:py-12">
            <div className="relative flex min-h-0 flex-1 items-center justify-center">
              <img
                src={photos[activeIndex]}
                alt={title}
                // contain, never cover - a viewer must not crop the photo.
                className="max-h-full max-w-full object-contain"
              />

              {count > 1 && (
                <>
                  <button
                    type="button"
                    onClick={() => step(-1)}
                    aria-label="Previous photo"
                    className={`${arrow} left-0`}
                  >
                    <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M15 5l-7 7 7 7" stroke="currentColor" strokeWidth="1.5" fill="none" />
                    </svg>
                  </button>

                  <button
                    type="button"
                    onClick={() => step(1)}
                    aria-label="Next photo"
                    className={`${arrow} right-0`}
                  >
                    <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M9 5l7 7-7 7" stroke="currentColor" strokeWidth="1.5" fill="none" />
                    </svg>
                  </button>
                </>
              )}
            </div>

            <p className="mt-4 text-center text-badge uppercase text-surface/70">
              {activeIndex + 1} / {count}
            </p>

            {count > 1 && (
              <div
                className="mt-4 flex shrink-0 justify-center gap-2 overflow-x-auto pb-1"
                style={{ scrollbarWidth: 'thin' }}
              >
                {photos.map((src, index) => (
                  <button
                    key={src}
                    type="button"
                    aria-label={`Photo ${index + 1} of ${count}`}
                    onClick={() => setActiveIndex(index)}
                    className={`h-16 w-16 shrink-0 overflow-hidden border transition-opacity ${
                      index === activeIndex
                        ? 'border-surface'
                        : 'border-transparent opacity-50 hover:opacity-100'
                    }`}
                  >
                    <img src={src} alt="" className="h-full w-full object-cover" />
                  </button>
                ))}
              </div>
            )}
          </div>
        </Modal>
      )}
    </>
  )
}

export default Gallery
