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
