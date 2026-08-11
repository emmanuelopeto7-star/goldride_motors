import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import { useMediaQuery } from '../hooks/useMediaQuery'

function Hero({ count }) {
  // Hooks first, always - an early return below must not change how many run.
  const isDesktop = useMediaQuery('(min-width: 768px)')
  const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)')

  const { data: banner } = useQuery({
    queryKey: ['hero'],
    queryFn: async () => {
      const res = await api.get('/api/hero/')
      // No active banner comes back as an empty body, not as null.
      return res.data || null
    },
  })

  if (!banner) return null

  const showVideo = Boolean(banner.video) && isDesktop && !reducedMotion

  return (
    <section className="relative h-svh w-full overflow-hidden bg-ink">
      {showVideo ? (
        <video
          src={banner.video}
          poster={banner.image}
          autoPlay
          muted
          loop
          playsInline
          className="h-full w-full object-cover"
        />
      ) : (
        <img
          src={banner.image}
          alt=""
          fetchPriority="high"
          className="h-full w-full object-cover"
        />
      )}

      {/* The one place a gradient is allowed: it earns white text over an
          arbitrary photograph, and it carries the header in overlay mode. */}
      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            'linear-gradient(to right, rgba(26, 26, 26, 0.45), rgba(26, 26, 26, 0))',
        }}
      />

      <div className="absolute bottom-5 left-5 max-w-[900px] lg:bottom-12 lg:left-12">
        <h1 className="font-serif text-[36px] leading-[1.05] text-surface lg:text-hero">
          {banner.headline}
        </h1>
        <p className="mt-4 text-badge uppercase text-surface/80">
          {banner.subline ? `${banner.subline} · ` : ''}
          {count} cars available
        </p>
      </div>
    </section>
  )
}

export default Hero
