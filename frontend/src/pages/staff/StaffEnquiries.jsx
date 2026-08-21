import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import api from '../../api/client'
import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'

/** Every "please contact me" a customer has sent about a car.
 *
 *  Read-only, because the endpoint is. Replying happens by phone or email
 *  today; when the ticket system lands these become tickets with an owner,
 *  which is the whole reason this list is worth having in front of someone
 *  now rather than sitting unread behind Swagger.
 */
function StaffEnquiries() {
  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ['staff-enquiries'],
    queryFn: async () => {
      const res = await api.get('/api/inquiries/all/')
      return res.data.results ?? res.data
    },
  })

  if (isPending) return <div className="h-64 w-full animate-pulse bg-line" />

  if (isError) {
    return (
      <ErrorState message="We could not load the enquiries." onRetry={refetch} />
    )
  }

  if (data.length === 0) {
    return (
      <EmptyState
        title="No enquiries"
        message="Messages sent from a car's page appear here."
      />
    )
  }

  return (
    <ul className="space-y-4">
      {data.map((enquiry) => (
        <li key={enquiry.id} className="border border-line bg-surface p-6">
          <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
            <div>
              <p className="text-model">{enquiry.car_display}</p>
              <p className="mt-1 text-meta text-ink-soft">
                {enquiry.name}
                {/* Only set when they were signed in - an enquiry can come
                    from a name typed into a form. */}
                {enquiry.customer_username && ` · ${enquiry.customer_username}`}
              </p>
            </div>

            <dl className="flex flex-wrap gap-x-10 gap-y-3 text-meta">
              <div>
                <dt className="text-ink-soft">Phone</dt>
                <dd className="mt-1">{enquiry.phone}</dd>
              </div>
              <div>
                <dt className="text-ink-soft">Email</dt>
                <dd className="mt-1">{enquiry.email || 'Not given'}</dd>
              </div>
              <div>
                <dt className="text-ink-soft">Sent</dt>
                <dd className="mt-1">
                  {new Date(enquiry.created_at).toLocaleDateString('en-KE')}
                </dd>
              </div>
            </dl>
          </div>

          {enquiry.message && (
            <p className="mt-4 max-w-[68ch] whitespace-pre-line border-t border-line pt-4 text-meta leading-relaxed text-ink-soft">
              {enquiry.message}
            </p>
          )}

          {enquiry.car && (
            <Link
              to={`/cars/${enquiry.car}`}
              className="mt-4 inline-block text-meta text-ink underline"
            >
              The car they asked about
            </Link>
          )}
        </li>
      ))}
    </ul>
  )
}

export default StaffEnquiries
