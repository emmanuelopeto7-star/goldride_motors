import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import { logoFor } from '../lib/makeLogos'

/** §8.1 — 1:1 bordered tiles, 8 / 4 / 3 across, with the maker named beneath
 *  its logo.
 *
 *  Logos stay in full colour. §8.1 originally called for greyscale until
 *  hover, which reads well on a wall of identical product shots but not here:
 *  these marks are the only colour on the page, and desaturating them makes
 *  the grid look disabled rather than restrained. Colour is also how people
 *  actually find a brand at a glance.
 *
 *  A make with no logo file falls back to its name in the display serif. That
 *  is not a placeholder to remove later: stock will eventually include
 *  something nobody has a file for, and a blank tile would be worse than a
 *  named one.
 */
function MakeGrid() {
  const { data: makes } = useQuery({
    queryKey: ['makes'],
    queryFn: async () => {
      const res = await api.get('/api/cars/makes/')
      return res.data
    },
  })

  if (!makes || makes.length === 0) return null

  return (
    <section className="mt-24">
      <h2 className="font-serif text-section">Browse by make</h2>

      <div className="mt-8 grid grid-cols-3 gap-3 md:grid-cols-4 lg:grid-cols-8">
        {makes.map(({ make, count }) => {
          const logo = logoFor(make)

          return (
            <Link
              key={make}
              to={`/?make=${encodeURIComponent(make)}`}
              // p-2 below md: on a 104px tile that is the 8px which lets
              // "Mercedes-Benz" hold one line. It needs 84 and p-3 leaves 80.
              className="group flex aspect-square flex-col items-center justify-center overflow-hidden border border-line bg-surface p-2 text-center transition-colors hover:border-ink md:p-3"
            >
              {logo ? (
                <>
                  <img
                    src={logo}
                    // Decorative: the make is written underneath, and a filled
                    // alt would have a screen reader announce it twice.
                    alt=""
                    loading="lazy"
                    // flex-1 with min-h-0, not a fixed height: a long name like
                    // Mercedes-Benz wraps to two lines in a narrow tile, and a
                    // rigid logo would push the tile taller than it is wide -
                    // breaking the 1:1 the whole grid depends on. The logo
                    // gives up the space instead.
                    //
                    // Contained, not cropped: these are different shapes - a
                    // wide Land Rover oval and a square Volvo ring - and cover
                    // would clip whichever way the tile does not fit.
                    className="min-h-0 w-[70%] flex-1 object-contain"
                  />
                  {/* Smaller on a narrow tile so the longest name - Mercedes-
                      Benz - still sits on one line. Wrapping is survivable
                      thanks to the flexible logo above, but it squeezes that
                      logo down to nothing, which defeats the point of it. */}
                  <span className="mt-2 text-[11px] leading-tight md:text-meta">
                    {make}
                  </span>
                </>
              ) : (
                // No logo on file, so the name carries the tile on its own and
                // can afford the display serif.
                <span className="font-serif text-[15px] leading-tight">{make}</span>
              )}

              <span className="mt-1 text-badge uppercase text-ink-mute">{count}</span>
            </Link>
          )
        })}
      </div>
    </section>
  )
}

export default MakeGrid
