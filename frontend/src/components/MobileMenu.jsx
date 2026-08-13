import { useEffect, useRef } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'
import Modal from './Modal'

const BODY_LINKS = [
  ['', 'All cars'],
  ['suv', 'SUVs'],
  ['pickup', 'Pickups'],
  ['saloon', 'Saloons'],
  ['hatchback', 'Hatchbacks'],
  ['van', 'Vans'],
]

const ACCOUNT_LINKS = [
  ['/my/orders', 'Orders'],
  ['/my/requests', 'Requests'],
  ['/my/saved', 'Saved'],
  ['/my/enquiries', 'Enquiries'],
  ['/my/profile', 'Profile'],
]

function MobileMenu({ onClose, onSignIn }) {
  const location = useLocation()
  const { user, isSales, signOut } = useAuth()

  // Shares the cache entry with the filter bar and footer.
  const { data: makes } = useQuery({
    queryKey: ['makes'],
    queryFn: async () => {
      const res = await api.get('/api/cars/makes/')
      return res.data
    },
  })

  // Navigating away should close it, or the panel sits over the page you just
  // asked for. Compare where we opened against where we are now - counting
  // runs does not survive StrictMode, which invokes every effect twice and
  // would close the drawer the instant it opened.
  const openedAt = useRef(location.pathname + location.search)
  useEffect(() => {
    if (location.pathname + location.search !== openedAt.current) onClose()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname, location.search])

  const heading = 'text-badge uppercase text-ink-mute'
  const link = 'block py-2 text-model text-ink'

  return (
    <Modal onClose={onClose} size="drawer">
      <p className="font-serif text-[22px] tracking-[0.08em]">GOLDRIDE</p>

      <nav className="mt-8">
        <p className={heading}>Browse</p>
        <ul className="mt-3">
          {BODY_LINKS.map(([value, label]) => (
            <li key={label}>
              <Link to={value ? `/?body_type=${value}` : '/'} className={link}>
                {label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      {(makes ?? []).length > 0 && (
        <nav className="mt-8 border-t border-line pt-8">
          <p className={heading}>Makes</p>
          <ul className="mt-3">
            {makes.slice(0, 8).map(({ make, count }) => (
              <li key={make}>
                <Link to={`/?make=${encodeURIComponent(make)}`} className={link}>
                  {make} <span className="text-ink-mute">({count})</span>
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      )}

      {isSales && (
        <nav className="mt-8 border-t border-line pt-8">
          <p className={heading}>Staff</p>
          <ul className="mt-3">
            <li>
              <Link to="/staff/approvals" className={link}>
                Approvals
              </Link>
            </li>
          </ul>
        </nav>
      )}

      <div className="mt-8 border-t border-line pt-8">
        {user ? (
          <>
            <p className={heading}>My account</p>
            <ul className="mt-3">
              {ACCOUNT_LINKS.map(([to, label]) => (
                <li key={to}>
                  <Link to={to} className={link}>
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
            <button
              type="button"
              onClick={() => {
                signOut()
                onClose()
              }}
              className="mt-6 h-12 w-full border border-ink text-badge uppercase"
            >
              Sign out
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={() => {
              onClose()
              onSignIn()
            }}
            className="h-12 w-full bg-ink text-badge uppercase text-surface"
          >
            Sign in
          </button>
        )}
      </div>
    </Modal>
  )
}

export default MobileMenu
