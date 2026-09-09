import heroImage from '../assets/hero.jpg'
import { counted } from '../lib/format'

/** The front door.
 *
 *  The image and the words are part of the build rather than rows in a table.
 *  They were editable from the staff settings screen once, and the cost of
 *  that was a network request before the first paint, a loading state to hold
 *  the dark band while it arrived, and - on a host with no persistent disk -
 *  an uploaded photograph that vanished on the next deploy, leaving a 404
 *  where the hero should be.
 *
 *  A hero that changes twice a year does not need a database behind it. The
 *  one thing here that is genuinely live is the car count, which is passed in.
 */

const HEADLINE = 'GOLDRIDE'
const SUBLINE =
  'Explore luxury cars, supercars and exotic cars for sale worldwide in one simple search'

function Hero({ count }) {
  return (
    <section className="relative h-svh w-full overflow-hidden bg-ink">
      <img
        src={heroImage}
        alt=""
        // Decorative: the headline over it carries the meaning, so an alt
        // description here would just be read out twice.
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

      <div className="absolute bottom-5 left-5 max-w-[900px] lg:bottom-12 lg:left-12">
        <h1 className="font-serif text-[36px] leading-[1.05] text-surface lg:text-hero">
          {HEADLINE}
        </h1>
        <p className="mt-4 text-badge uppercase text-surface/80">
          {SUBLINE} · {counted(count, 'car')} available
        </p>
      </div>
    </section>
  )
}

export default Hero
