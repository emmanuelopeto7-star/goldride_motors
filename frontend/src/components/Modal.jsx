import { useEffect } from 'react'
import { createPortal } from 'react-dom'

/** size="dialog" is the 440px card used for auth and forms.
 *  size="full" is an edge-to-edge dark surface for viewing images.
 *  size="drawer" is a full-height panel against the left edge, for navigation. */
function Modal({ onClose, children, size = 'dialog' }) {
  useEffect(() => {
    function handleKey(event) {
      if (event.key === 'Escape') onClose()
    }

    document.addEventListener('keydown', handleKey)
    document.body.style.overflow = 'hidden'

    // Every effect that adds something must return the code that removes it,
    // or the page stays unscrollable after the modal is gone.
    return () => {
      document.removeEventListener('keydown', handleKey)
      document.body.style.overflow = ''
    }
  }, [onClose])

  const full = size === 'full'
  const drawer = size === 'drawer'

  // Rendered into document.body, not where it is written. A modal inside a
  // sticky or transformed ancestor is trapped in that stacking context, and
  // no z-index can lift it above the header from in there.
  return createPortal(
    <div
      className={`fixed inset-0 z-[100] flex ${
        full
          ? 'items-center justify-center bg-ink/95'
          : drawer
            ? 'items-stretch justify-start bg-ink/50'
            : // Scroll the scrim, not the dialog, so a tall form is reachable
              // on a short screen instead of being clipped at both ends.
              'items-start justify-center overflow-y-auto bg-ink/50 px-5 py-10'
      }`}
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        className={
          full
            ? 'relative h-full w-full'
            : drawer
              ? 'relative h-full w-full max-w-[360px] overflow-y-auto border-r border-line bg-page p-8'
              : 'relative my-auto w-full max-w-[440px] border border-line bg-page p-8 lg:p-12'
        }
        // Stops a click inside the panel bubbling up to the scrim's close.
        onClick={(event) => event.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className={`absolute z-10 flex h-8 w-8 items-center justify-center rounded-full ${
            full ? 'right-5 top-5 text-surface' : 'right-4 top-4'
          }`}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M5 5l14 14M19 5L5 19" stroke="currentColor" strokeWidth="1.5" />
          </svg>
        </button>

        {children}
      </div>
    </div>,
    document.body,
  )
}

export default Modal
