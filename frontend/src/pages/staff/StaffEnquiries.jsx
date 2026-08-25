import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import api from '../../api/client'
import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import Pagination from '../../components/Pagination'

/** Every "please contact me" a customer has sent about a car.
 *
 *  Read-only, because the endpoint is. Replying happens by phone or email
 *  today; when the ticket system lands these become tickets with an owner,
 *  which is the whole reason this list is worth having in front of someone
 *  now rather than sitting unread behind Swagger.
 */
function StaffEnquiries() {
  const [searchParams] = useSearchParams()
  const page = Math.max(1, Number(searchParams.get('page') ?? 1))

  const { data, isPending, isError, refetch } = useQuery({
    // The whole payload, not just the results. The endpoint paginates at
    // twelve, so returning only the first page made every enquiry after the
    // twelfth unreachable - invisible rather than merely further down.
    queryKey: ['staff-enquiries', page],
    queryFn: async () => {
      const res = await api.get('/api/inquiries/all/', {
        params: page > 1 ? { page } : undefined,
      })
      const payload = res.data
      return Array.isArray(payload)
        ? { results: payload, count: payload.length, next: null, previous: null }
        : payload
    },
  })

  if (isPending) return <div className="h-64 w-full animate-pulse bg-line" />

  if (isError) {
    return (
      <ErrorState message="We could not load the enquiries." onRetry={refetch} />
    )
  }

  const enquiries = data.results

  if (enquiries.length === 0) {
    return (
      <EmptyState
        title="No enquiries"
        message="Messages sent from a car's page appear here."
      />
    )
  }

  return (
    <>
      <ul className="space-y-4">
        {enquiries.map((enquiry) => (
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

      <Pagination
        count={data.count}
        hasNext={Boolean(data.next)}
        hasPrevious={Boolean(data.previous)}
      />
    </>
  )
}

export default StaffEnquiries
