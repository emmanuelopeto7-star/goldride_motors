/** Is the home page being used as a shopfront, or as a result set?
 *
 *  `/` with no parameters is the front door: full-height hero, brand strip,
 *  browse aids. `/?make=Toyota` is a result set that happens to live at the
 *  same path — and rendering the front door for it drops you at a 100vh
 *  photograph with the nine Toyotas you asked for somewhere below the fold.
 *
 *  Layout and Home both need this answer and must never disagree: Layout uses
 *  it to decide whether the header is transparent over a hero, Home to decide
 *  whether there is a hero at all. Two copies of the rule would eventually
 *  drift into white header text on a white page.
 */

/** Everything that turns the page into a result set. `ordering` counts: if you
 *  have sorted, you are looking at results, not arriving. */
export const BROWSE_PARAMS = [
  'search',
  'make',
  'body_type',
  'fuel_type',
  'transmission',
  'ordering',
]

export function isBrowsing(searchParams) {
  if (BROWSE_PARAMS.some((key) => searchParams.get(key))) return true
  // Page 2 of an unfiltered list is still browsing - nobody wants to scroll
  // past the hero again to reach it.
  return Number(searchParams.get('page') ?? 1) > 1
}

/** What to call this result set, in the user's words rather than the API's. */
export function browsingTitle(searchParams) {
  const search = searchParams.get('search')
  if (search) return `“${search}”`

  const make = searchParams.get('make')
  const body = searchParams.get('body_type')
  const fuel = searchParams.get('fuel_type')
  const transmission = searchParams.get('transmission')

  const parts = [
    fuel && fuel.charAt(0).toUpperCase() + fuel.slice(1),
    transmission && transmission.charAt(0).toUpperCase() + transmission.slice(1),
    make,
    body && (body === 'suv' ? 'SUVs' : `${body.charAt(0).toUpperCase()}${body.slice(1)}s`),
  ].filter(Boolean)

  return parts.length > 0 ? parts.join(' · ') : 'All cars'
}
