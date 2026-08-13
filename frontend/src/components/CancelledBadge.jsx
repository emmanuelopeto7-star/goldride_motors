/** Marks an import order that was called off.
 *
 *  Solid ink rather than a colour: the palette has no red, and inventing one
 *  for a single badge would put a second accent on a page that has none. The
 *  filled pill is already the strongest thing the design system says, which is
 *  the whole point - a cancelled order previously looked identical to a live
 *  one sitting at "Ordered".
 */
function CancelledBadge({ className = '' }) {
  return (
    <span
      className={`inline-block rounded-full bg-ink px-3 py-1 text-badge uppercase text-surface ${className}`}
    >
      Request cancelled
    </span>
  )
}

export default CancelledBadge
