import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import ErrorState from '../components/ErrorState'
import OrderProgress from '../components/OrderProgress'
import Page from '../components/Page'

/** Public, reached from the link we email a customer. No sign-in: the UUID in
 *  the URL is the credential, which is why the endpoint exposes only the car
 *  description and its milestones - no name, no phone, no id. */
function TrackOrder() {
  const { token } = useParams()

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ['track', token],
    queryFn: async () => {
      const res = await api.get(`/api/track/${token}/`)
      return res.data
    },
    retry: false,
  })

  if (isPending) {
    return (
      <Page>
        <div className="h-8 w-64 animate-pulse bg-line" />
        <div className="mt-8 h-40 w-full max-w-[640px] animate-pulse bg-line" />
      </Page>
    )
  }

  if (isError) {
    const missing = error?.response?.status === 404
    const throttled = error?.response?.status === 429
    return (
      <Page>
        <ErrorState
          title={missing ? 'Tracking link not found' : 'Something went wrong'}
          message={
            missing
              ? 'Check the link in your email — it may have been copied incompletely.'
              : throttled
                ? 'Too many checks in a short time. Try again shortly.'
                : 'We could not load this order.'
          }
          onRetry={missing ? undefined : refetch}
        />
      </Page>
    )
  }

  return (
    <Page>
      <p className="text-badge uppercase text-ink-soft">Import tracking</p>
      <h1 className="mt-3 font-serif text-h1">{data.car_description}</h1>

      <div className="mt-10 border border-line bg-surface p-6 lg:p-8">
        <OrderProgress currentStage={data.current_stage} />

        {data.milestones?.length > 0 ? (
          <ol className="mt-8 space-y-4 border-t border-line pt-8">
            {data.milestones.map((milestone) => (
              <li key={`${milestone.stage}-${milestone.created_at}`}>
                <p className="text-badge uppercase text-ink-soft">
                  {milestone.stage.replace('_', ' ')} ·{' '}
                  {new Date(milestone.created_at).toLocaleDateString('en-KE')}
                </p>
                {milestone.note && (
                  <p className="mt-1 text-model text-ink-soft">{milestone.note}</p>
                )}
              </li>
            ))}
          </ol>
        ) : (
          <p className="mt-8 border-t border-line pt-8 text-model text-ink-soft">
            No updates recorded yet. We will add each stage as it happens.
          </p>
        )}
      </div>

      <p className="mt-8 text-meta text-ink-mute">
        Keep this link — it is the only way to reach this page, and anyone with
        it can see this progress.
      </p>

      <Link to="/" className="mt-8 inline-block text-meta text-ink underline">
        Browse cars
      </Link>
    </Page>
  )
}

export default TrackOrder
