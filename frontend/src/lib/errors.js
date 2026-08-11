export function errorMessages(error) {
  const data = error?.response?.data

  if (!data) return ['Something went wrong. Please try again.']
  if (typeof data === 'string') return [data]

  return Object.values(data).flat()
}