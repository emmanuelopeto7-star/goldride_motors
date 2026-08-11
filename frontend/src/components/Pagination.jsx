import { Link, useSearchParams } from 'react-router-dom'

/** Must match DEFAULT_PAGINATION PAGE_SIZE in the Django settings. The arrows
 *  are driven by the API's own next/previous, so if these ever drift the
 *  numbers are wrong but navigation still works. */
const PAGE_SIZE = 12

/** 1 … 4 5 6 … 12 - a window around the current page once there are too many
 *  to list. */
function pageItems(current, total) {
  if (total <= 7) {
    return Array.from({ length: total }, (_, index) => index + 1)
  }

  const items = new Set([1, total, current, current - 1, current + 1])
  const pages = [...items].filter((page) => page >= 1 && page <= total).sort((a, b) => a - b)

  const withGaps = []
  pages.forEach((page, index) => {
    if (index > 0 && page - pages[index - 1] > 1) withGaps.push(`gap-${page}`)
    withGaps.push(page)
  })

  return withGaps
}

function Pagination({ count, hasNext, hasPrevious }) {
  const [searchParams] = useSearchParams()
  const current = Math.max(1, Number(searchParams.get('page') ?? 1))
  const total = Math.ceil(count / PAGE_SIZE)

  if (total <= 1) return null

  // Keep every other filter intact - only the page changes.
  function hrefFor(page) {
    const params = new URLSearchParams(searchParams)
    if (page === 1) params.delete('page')
    else params.set('page', String(page))
    const query = params.toString()
    return query ? `/?${query}` : '/'
  }

  const base =
    'flex h-10 min-w-10 items-center justify-center rounded-full border px-4 text-meta transition-colors'

  return (
    <nav
      aria-label="Pagination"
      className="mt-16 flex flex-wrap items-center justify-center gap-3"
    >
      {hasPrevious ? (
        <Link to={hrefFor(current - 1)} className={`${base} border-line hover:border-ink`}>
          Previous
        </Link>
      ) : (
        <span className={`${base} border-line text-ink-mute`}>Previous</span>
      )}

      {pageItems(current, total).map((item) =>
        typeof item === 'string' ? (
          <span key={item} className="px-1 text-meta text-ink-mute">
            …
          </span>
        ) : (
          <Link
            key={item}
            to={hrefFor(item)}
            aria-current={item === current ? 'page' : undefined}
            className={`${base} ${
              item === current
                ? 'border-ink bg-ink text-surface'
                : 'border-line hover:border-ink'
            }`}
          >
            {item}
          </Link>
        ),
      )}

      {hasNext ? (
        <Link to={hrefFor(current + 1)} className={`${base} border-line hover:border-ink`}>
          Next
        </Link>
      ) : (
        <span className={`${base} border-line text-ink-mute`}>Next</span>
      )}
    </nav>
  )
}

export default Pagination
