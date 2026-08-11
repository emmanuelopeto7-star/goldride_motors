import { useState } from 'react'
import {
  Link,
  Outlet,
  useLocation,
  useNavigate,
  useSearchParams,
} from 'react-router-dom'
import api from '../api/client'
import { getToken, clearToken } from '../lib/auth'
import { useScrolled } from '../hooks/useScrolled'
import AuthModal from './AuthModal'
import BrandStrip from './BrandStrip'

const pillBase =
  'flex h-10 shrink-0 items-center rounded-full border px-5 text-meta transition-colors duration-200'

function Layout() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const [term, setTerm] = useState(searchParams.get('search') ?? '')
  const [authOpen, setAuthOpen] = useState(false)
  const [signedIn, setSignedIn] = useState(Boolean(getToken()))

  const scrolled = useScrolled(80)
  // Only the home page has a hero, so only it can be overlaid (§4.6).
  const hasHero = location.pathname === '/'
  const overlay = hasHero && !scrolled

  async function handleSignOut() {
    try {
      await api.post('/api/auth/logout/')
    } catch {
      // The token may already be dead server-side; clear it locally regardless.
    }
    clearToken()
    setSignedIn(false)
  }

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
        <div className="mx-auto flex h-[72px] max-w-[1440px] items-center gap-6 px-5 lg:px-12">
          <button type="button" aria-label="Open menu" className="shrink-0">
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
                  ? 'border border-white/25 bg-white/15 text-surface placeholder-white/70'
                  : 'bg-search text-ink'
              }`}
            />
          </form>

          {signedIn ? (
            <button
              type="button"
              onClick={handleSignOut}
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

        <BrandStrip overlay={overlay} />
      </header>

      <main>
        <Outlet />
      </main>

      {authOpen && (
        <AuthModal
          onClose={() => setAuthOpen(false)}
          onSignedIn={() => setSignedIn(true)}
        />
      )}
    </div>
  )
}

export default Layout
