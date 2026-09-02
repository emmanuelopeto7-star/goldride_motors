export function formatPrice(value) {
    return new Intl.NumberFormat('en-KE', {
    style: 'currency',
    currency: 'KES',
    currencyDisplay: 'code',
    maximumFractionDigits: 0,
  }).format(Number(value))
}

/** The right word for a count.
 *
 *  Every screen that shows "N somethings" was solving this separately, and
 *  four of them were not solving it at all - a listing with one photograph
 *  read "1 PHOTOS" on its own detail page. One helper so the next person to
 *  write a count does not have to remember, and cannot get it wrong.
 *
 *  `plural` is only needed for words that do not just take an s.
 */
export function pluralise(count, singular, plural = `${singular}s`) {
  return Number(count) === 1 ? singular : plural
}

/** "1 photo", "12 photos", "1,248 cars" - the number and its noun together,
 *  with thousands separators, which a bare template string loses. */
export function counted(count, singular, plural) {
  const n = Number(count) || 0
  return `${n.toLocaleString('en-KE')} ${pluralise(n, singular, plural)}`
}

/** A price short enough for a chart axis: "1.5M", "250K", "0".
 *
 *  Not a replacement for formatPrice - an axis has room for five characters
 *  and a tooltip has room for the real figure, so both exist and the chart
 *  uses each where it fits.
 */
export function compactPrice(value) {
  const amount = Number(value) || 0
  const sign = amount < 0 ? '-' : ''
  const size = Math.abs(amount)

  if (size >= 1_000_000) return `${sign}${trimZero(size / 1_000_000)}M`
  if (size >= 1_000) return `${sign}${trimZero(size / 1_000)}K`
  return `${sign}${Math.round(size)}`
}

function trimZero(value) {
  // 1.5M keeps its half; 2.0M is just 2M.
  const rounded = value >= 10 ? Math.round(value) : Math.round(value * 10) / 10
  return String(rounded)
}
