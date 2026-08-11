import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import EmptyState from '../components/EmptyState'
import ErrorState from '../components/ErrorState'

function MyEnquiries() {
  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ['my-enquiries'],
    queryFn: async () => {
      const res = await api.get('/api/inquiries/')
      return res.data
    },
  })

  if (isPending) return <div className="h-64 w-full animate-pulse bg-line" />

  if (isError) {
    return <ErrorState message="We could not load your enquiries." onRetry={refetch} />
  }

  const enquiries = data.results ?? data

  if (enquiries.length === 0) {
    return (
      <EmptyState
        title="No enquiries yet"
        message="Questions you send about a car are kept here."
        action={
          <Link to="/" className="mt-8 inline-block text-meta text-ink underline">
            Browse cars
          </Link>
        }
      />
    )
  }

  return (
    <div className="space-y-4">
      {enquiries.map((enquiry) => (
        <article key={enquiry.id} className="border border-line bg-surface p-6">
          <div className="flex flex-wrap items-baseline justify-between gap-4">
            <h2 className="text-model">
              <Link to={`/cars/${enquiry.car}`} className="underline">
                {enquiry.car_display}
              </Link>
            </h2>
            <span className="text-meta text-ink-soft">
              {new Date(enquiry.created_at).toLocaleDateString('en-KE')}
            </span>
          </div>

          {enquiry.message && (
            <p className="mt-3 whitespace-pre-line text-model text-ink-soft">
              {enquiry.message}
            </p>
          )}

          <p className="mt-3 text-meta text-ink-mute">
            Sent from {enquiry.phone}
          </p>
        </article>
      ))}
    </div>
  )
}

export default MyEnquiries
