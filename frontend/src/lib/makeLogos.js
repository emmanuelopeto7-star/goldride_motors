/** Manufacturer logos, keyed by make.
 *
 *  Globbed rather than listed as seventeen imports so that dropping a new file
 *  into assets/logos is the whole job — the alternative is a hand-written map
 *  that silently goes stale the first time stock includes a make nobody
 *  remembered to add.
 *
 *  Vite hashes and fingerprints each file at build time, so these cache
 *  forever and bust correctly when a logo is replaced.
 */

const files = import.meta.glob('../assets/logos/*.png', {
  eager: true,
  query: '?url',
  import: 'default',
})

const byMake = Object.fromEntries(
  Object.entries(files).map(([path, url]) => [
    path.split('/').pop().replace('.png', ''),
    url,
  ]),
)

/** "Mercedes-Benz" -> "mercedes-benz", "Land Rover" -> "land-rover". */
export function makeSlug(make) {
  return make.toLowerCase().trim().replace(/\s+/g, '-')
}

/** The logo for a make, or null. Null is a normal answer: stock can include a
 *  make we have no file for, and the tile falls back to its name. */
export function logoFor(make) {
  return byMake[makeSlug(make)] ?? null
}
