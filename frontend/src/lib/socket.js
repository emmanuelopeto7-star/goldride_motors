/** The websocket address for a path, derived from the API's own.
 *
 *  Derived rather than configured: a second environment variable that has to
 *  agree with the first is a second thing to get wrong, and it only ever
 *  fails in production where the scheme differs.
 */
export function socketUrl(path) {
  const base = import.meta.env.VITE_API_URL || window.location.origin
  const url = new URL(path, base)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  return url.toString()
}
