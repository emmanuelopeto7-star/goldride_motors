import { useState } from 'react'
import {
  Link,
  Outlet,
  useLocation,
  useNavigate,
  useSearchParams,
} from 'react-router-dom'
import { useScrolled } from '../hooks/useScrolled'
import { useHeroBanner } from '../hooks/useHeroBanner'
import { useAuth } from '../context/AuthContext'
import AuthModal from './AuthModal'
import BrandStrip from './BrandStrip'
import Footer from './Footer'
import MobileMenu from './MobileMenu'

const pillBase =
  'flex h-10 shrink-0 items-center rounded-full border px-5 text-meta transition-colors duration-200'

function Layout() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const [term, setTerm] = useState(searchParams.get('search') ?? '')
  const [authOpen, setAuthOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const { user, isSales, signOut } = useAuth()

  const scrolled = useScrolled(80)
  // Shares a cache entry with Hero, so this costs no extra request. Keyed on
  // whether a hero will actually draw, not merely on the route - otherwise a
  // home page with no banner leaves white header text on a white background.
  const { data: banner, isPending: bannerPending } = useHeroBanner()
  const hasHero = location.pathname === '/' && (bannerPending || Boolean(banner))
  const overlay = hasHero && !scrolled

  function handleSubmit(event) {
    event.preventDefault()
    const query = term.trim()
    navigate(query ? `/?search=${encodeURIComponent(query)}` : '/')
  }

  return (
    <div className="min-h-screen bg-page text-ink">
      <header
        className={`${hasHero ? 'fixed' : 'sticky'} top-0 z-50 w-full transition-colors duration-200 ${
          overlay ? 'text-surface' : 'border-b border-line bg-surface text-ink'
        }`}
      >
        {/* Full width, not the §3.4 container: the nav reads as chrome and
            belongs against the screen edges, while page content stays in the
            1440px column below it. */}
        <div className="flex h-[72px] w-full items-center gap-6 px-5 lg:px-12">
          <button
            type="button"
            aria-label="Open menu"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen(true)}
            className="shrink-0"
          >
            <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M3 6h18M3 12h18M3 18h18" stroke="currentColor" strokeWidth="1.5" />
            </svg>
          </button>

          <Link to="/" className="shrink-0 font-serif text-[22px] tracking-[0.08em]">
            GOLDRIDE
          </Link>

          <form onSubmit={handleSubmit} className="max-w-[620px] flex-1">
            <input
              type="search"
              value={term}
              onChange={(event) => setTerm(event.target.value)}
              placeholder="Search make or model"
              className={`h-11 w-full rounded-full px-5 text-meta outline-none transition-colors duration-200 ${
                overlay
                  ? 'border border-white/25 bg-white/15 text-surface placeholder:text-white/70'
                  : 'bg-search text-ink placeholder:text-ink-mute'
              }`}
            />
          </form>

          {/* ml-auto, not flex-1 on the form: the search is capped at 620px,
              so it cannot absorb the slack on a wide screen and the right-hand
              items would sit stranded in the middle. */}
          <div className="ml-auto flex shrink-0 items-center gap-6">
          {/* Only staff see it, so it costs a customer nothing. The route is
              guarded and the API re-checks regardless - this is a shortcut,
              not the permission. */}
          {isSales && (
            <Link
              to="/staff"
              className={`hidden shrink-0 text-meta underline lg:block ${
                overlay ? 'text-surface' : 'text-ink'
              }`}
            >
              Staff
            </Link>
          )}

          <Link
            to="/import"
            className={`hidden shrink-0 text-meta underline lg:block ${
              overlay ? 'text-surface' : 'text-ink'
            }`}
          >
            Import a car
          </Link>

          {user && (
            <Link
              to="/my/orders"
              className={`hidden shrink-0 text-meta underline lg:block ${
                overlay ? 'text-surface' : 'text-ink'
              }`}
            >
              My orders
            </Link>
          )}

          {user ? (
            <button
              type="button"
              onClick={signOut}
              className={`${pillBase} ${overlay ? 'border-white/40' : 'border-line'}`}
            >
              Sign out
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setAuthOpen(true)}
              className={`${pillBase} ${overlay ? 'border-white/40' : 'border-line'}`}
            >
              Sign in
            </button>
          )}
          </div>
        </div>

        <BrandStrip overlay={overlay} />
      </header>

      <main>
        <Outlet />
      </main>

      <Footer />

      {menuOpen && (
        <MobileMenu
          onClose={() => setMenuOpen(false)}
          onSignIn={() => setAuthOpen(true)}
        />
      )}

      {authOpen && <AuthModal onClose={() => setAuthOpen(false)} />}
    </div>
  )
}

export default Layout
