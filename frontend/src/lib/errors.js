export function errorMessages(error) {
  const data = error?.response?.data
  const fallback = 'Something went wrong. Please try again.'

  if (!data) return [fallback]

  // Not JSON - an HTML error page, a proxy, a gateway. Never show it raw.
  if (typeof data === 'string') {
    return [data.length > 200 || data.trimStart().startsWith('<') ? fallback : data]
  }

  return Object.values(data).flat()
}
