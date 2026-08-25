export function errorMessages(error) {
  const data = error?.response?.data
  const fallback = 'Something went wrong. Please try again.'

  if (!data) return [fallback]

  // Not JSON - an HTML error page, a proxy, a gateway. Never show it raw.
  if (typeof data === 'string') {
    return [data.length > 200 || data.trimStart().startsWith('<') ? fallback : data]
  }

  // `code` is for us to branch on, not for the customer to read. Without
  // this a refusal renders its own machine name underneath the sentence
  // explaining it - "protected" sitting under a perfectly good reason.
  return Object.entries(data)
    .filter(([key]) => key !== 'code')
    .map(([, value]) => value)
    .flat()
}
