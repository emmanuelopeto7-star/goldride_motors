import { useState } from 'react'
import { Link, Outlet, useNavigate, useSearchParams } from 'react-router-dom'

function Layout() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [term, setTerm] = useState(searchParams.get('search') ?? '')

  function handleSubmit(event) {
    event.preventDefault()
    const query = term.trim()
    navigate(query ? `/?search=${encodeURIComponent(query)}` : '/')
  }

  return (
    <div className="min-h-screen bg-page text-ink">
      <header className="sticky top-0 z-50 border-b border-line bg-surface">
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
              className="h-11 w-full rounded-full bg-search px-5 text-meta outline-none"
            />
          </form>


          <Link
            to="/login"
            className="flex h-10 shrink-0 items-center rounded-full border border-line px-5 text-meta"
          >
            Sign in
          </Link>
        </div>
      </header>

      <main>
        <Outlet />
      </main>
    </div>
  )
}

export default Layout