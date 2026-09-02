import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'

const BODY_LINKS = [
  ['', 'All cars'],
  ['suv', 'SUVs'],
  ['pickup', 'Pickups'],
  ['saloon', 'Saloons'],
  ['hatchback', 'Hatchbacks'],
  ['van', 'Vans'],
]

function Footer() {
  // Shares the cache entry with FilterBar, so this costs no extra request.
  const { data: makes } = useQuery({
    queryKey: ['makes'],
    queryFn: async () => {
      const res = await api.get('/api/cars/makes/')
      return res.data
    },
  })

  const topMakes = (makes ?? []).slice(0, 6)
  const year = new Date().getFullYear()

  const linkClass = 'text-meta text-surface/70 transition-colors hover:text-surface'
  const headingClass = 'text-badge uppercase text-surface/50'

  return (
    <footer className="mt-24 bg-ink text-surface">
      <div className="mx-auto max-w-[1440px] px-5 py-16 lg:px-12 lg:py-24">
        <div className="grid gap-12 md:grid-cols-2 lg:grid-cols-4">
          <div>
            <p className="font-serif text-[22px] tracking-[0.08em]">GOLDRIDE</p>
            <p className="mt-4 max-w-[280px] text-meta text-surface/70">
              Imported and locally sourced vehicles, inspected and documented
              before they reach the lot.
            </p>
          </div>

          <div>
            <p className={headingClass}>Browse</p>
            <ul className="mt-4 space-y-2">
              {BODY_LINKS.map(([value, label]) => (
                <li key={label}>
                  <Link to={value ? `/?body_type=${value}` : '/'} className={linkClass}>
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <p className={headingClass}>Makes</p>
            <ul className="mt-4 space-y-2">
              {topMakes.map(({ make, count }) => (
                <li key={make}>
                  <Link to={`/?make=${encodeURIComponent(make)}`} className={linkClass}>
                    {make} <span className="text-surface/40">({count})</span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <p className={headingClass}>Contact</p>
            <ul className="mt-4 space-y-2">
              <li>
                <a href="mailto:sales@goldridemotors.co.ke" className={linkClass}>
                  sales@goldridemotors.co.ke
                </a>
              </li>
              <li className="text-meta text-surface/70">Nairobi, Kenya</li>
              {/* §10.4 - it points at a page that exists. Boxed rather than
                  set as one more link in the column: a dealership arriving at
                  the bottom of the page is here on different business from
                  everybody else reading a contact list. */}
              <li className="pt-4">
                <Link
                  to="/list-with-us"
                  className="inline-block border border-white/40 px-5 py-3 text-meta text-surface transition-colors hover:border-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
                >
                  List your cars with us
                </Link>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-16 flex flex-wrap items-center justify-between gap-4 border-t border-white/15 pt-8">
          <p className="text-meta text-surface/50">
            © {year} Goldride Motors. All rights reserved.
          </p>
          <p className="text-meta text-surface/50">
            Vehicle details are provided in good faith. Confirm specification and
            condition before purchase.
          </p>
        </div>
      </div>
    </footer>
  )
}

export default Footer
