import { useMediaQuery } from '../hooks/useMediaQuery'
import { useHeroBanner } from '../hooks/useHeroBanner'

function Hero({ count }) {
  // Hooks first, always - the early returns below must not change how many run.
  const isDesktop = useMediaQuery('(min-width: 768px)')
  const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)')

  const { data: banner, isPending } = useHeroBanner()

  // Hold the dark band while the banner is in flight. Returning null would
  // strand the transparent header on a white page, white-on-white.
  if (isPending) return <div className="h-svh w-full bg-ink" />
  if (!banner) return null

  // §5b.5 and §5b.6: mobile and reduced-motion never load the video at all.
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
