import Button from './Button'
import ChatLauncher from './ChatLauncher'
import { useState } from 'react'
import {
  Link,
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
  useSearchParams,
} from 'react-router-dom'
import { useScrolled } from '../hooks/useScrolled'
import { useHeroBanner } from '../hooks/useHeroBanner'
import { useAuth } from '../context/AuthContext'
import { isBrowsing } from '../lib/browsing'
import AuthModal from './AuthModal'
import BrandStrip from './BrandStrip'
import Footer from './Footer'
import MobileMenu from './MobileMenu'

/** The text links in the header row.
 *
 *  **Underline means "you are here", not "this is a link".** §2.1 gives
 *  underline to links *and active states*, and these were underlined
 *  permanently - so all four claimed to be the current page at once, the row
 *  read as four competing emphases, and there was no mark left to show which
 *  page anybody was actually on. At rest they are plain; hover underlines to
 *  say it is clickable; the route you are on keeps the underline.
 *
 *  Secondary ink at rest, primary on hover and when active - three states in
 *  a palette with no colour in it, done with weight of ink rather than hue.
 *
 *  `py-3 -my-3` rather than a taller link: it grows the hit target to a
 *  comfortable size without changing where anything sits, because the row is
 *  vertically centred in a fixed 80px header. The focus ring is
 *  `outline-current` rather than the browser's - that default is orange, and
 *  §2.2 has no colour in it - which also inverts with the header for free.
 */
const NAV_LINK_BASE =
  'hidden shrink-0 py-3 -my-3 text-meta underline-offset-4 transition-colors duration-200 lg:block focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-current'

function navLinkClass({ isActive, overlay }) {
  // Over the hero the rest state stays full white and only the underline
  // separates active from not. The footer can dim its links to 70% because it
  // sits on a flat #1A1A1A and the contrast is a number you can check; here
  // the backdrop is whatever photograph marketing uploaded, and 70% white on
  // a bright patch of one is a link nobody can read.
  const rest = overlay ? 'text-surface' : 'text-ink-soft'
  const active = overlay ? 'text-surface' : 'text-ink'
  const hover = overlay ? '' : 'hover:text-ink'

  return [
    NAV_LINK_BASE,
    isActive ? `${active} underline` : `${rest} ${hover} hover:underline`,
  ]
    .filter(Boolean)
    .join(' ')
}

function Layout() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const [term, setTerm] = useState(searchParams.get('search') ?? '')
  const [authOpen, setAuthOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const { user, isSales, isDealer, signOut } = useAuth()

  const scrolled = useScrolled(80)
  // Shares a cache entry with Hero, so this costs no extra request. Keyed on
  // whether a hero will actually draw, not merely on the route - otherwise a
  // home page with no banner leaves white header text on a white background.
  const { data: banner, isPending: bannerPending } = useHeroBanner()
  // A filtered list lives at "/" too, but it is a result set rather than the
  // front door - so no hero, and the header is solid from the first paint.
  const browsing = isBrowsing(searchParams)
  const hasHero =
    location.pathname === '/' && !browsing && (bannerPending || Boolean(banner))
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
            <NavLink
              to="/staff"
              className={({ isActive }) => navLinkClass({ isActive, overlay })}
            >
              Staff
            </NavLink>
          )}

          <NavLink
              to="/import"
              className={({ isActive }) => navLinkClass({ isActive, overlay })}
            >
            Import a car
          </NavLink>

          {/* The way in for other dealerships. It lived only in the footer,
              which is a poor place for the one thing a visiting dealer came
              to do. Hidden from a dealer who is already signed in - they have
              their own area, and the application form is behind them. */}
          {!isDealer && (
            <NavLink
              to="/list-with-us"
              className={({ isActive }) => navLinkClass({ isActive, overlay })}
            >
              List your cars
            </NavLink>
          )}

          {isDealer && (
            <NavLink
              to="/dealer"
              className={({ isActive }) => navLinkClass({ isActive, overlay })}
            >
              Your cars
            </NavLink>
          )}

          {user && (
            <NavLink
              to="/my/orders"
              className={({ isActive }) => navLinkClass({ isActive, overlay })}
            >
              My orders
            </NavLink>
          )}

          {user ? (
            <Button
              variant="pill"
              onClick={signOut}
              className={overlay ? 'border-white/40' : 'border-line'}
            >
              Sign out
            </Button>
          ) : (
            <Button
              variant="pill"
              onClick={() => setAuthOpen(true)}
              className={overlay ? 'border-white/40' : 'border-line'}
            >
              Sign in
            </Button>
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

      {/* Every shopfront page, so a question can be asked from wherever it
          occurred to them rather than only from the account area. */}
      <ChatLauncher />
    </div>
  )
}

export default Layout
