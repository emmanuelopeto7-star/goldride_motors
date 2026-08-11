import { useQuery } from '@tanstack/react-query'
import api from '../api/client'

function Hero({ count }) {
  const { data: banner } = useQuery({
    queryKey: ['hero'],
    queryFn: async () => {
      const res = await api.get('/api/hero/')
      // No active banner comes back as an empty body, not as null.
      return res.data || null
    },
  })

  if (!banner) return null

  return (
    <section className="relative h-[280px] w-full overflow-hidden bg-ink lg:h-[420px]">
      <img
        src={banner.image}
        alt=""
        fetchPriority="high"
        className="h-full w-full object-cover"
      />

      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            'linear-gradient(to right, rgba(26, 26, 26, 0.45), rgba(26, 26, 26, 0))',
        }}
      />
       <div className="absolute bottom-5 left-5 max-w-[480px] lg:bottom-12 lg:left-12">
        <h1 className="font-serif text-h1 text-surface">{banner.headline}</h1>
        <p className="mt-3 text-badge uppercase text-surface/80">
          {banner.subline ? `${banner.subline} · ` : ''}
          {count} cars available
        </p>
      </div>
    </section>
  )
}

export default Hero