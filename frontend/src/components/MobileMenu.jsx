import { useEffect, useRef } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'
import Modal from './Modal'
import Button from './Button'

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
  const { user, isSales, isDealer, signOut } = useAuth()

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
  // py-3 keeps every row a comfortable target on a phone; py-2 put a
  // 15px link in a 36px box, which is under any reasonable minimum.
  const link =
    'block py-3 text-model text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-current'

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

      <nav className="mt-8 border-t border-line pt-8">
        <p className={heading}>Import</p>
        <ul className="mt-3">
          <li>
            <Link to="/import" className={link}>
              Import a car
            </Link>
          </li>
        </ul>
      </nav>

      {/* A dealership arriving on a phone has the same errand as one on a
          desktop, and the footer is even further away down here. */}
      <nav className="mt-8 border-t border-line pt-8">
        <p className={heading}>Dealers</p>
        <ul className="mt-3">
          <li>
            {isDealer ? (
              <Link to="/dealer" className={link}>
                Your cars
              </Link>
            ) : (
              <Link to="/list-with-us" className={link}>
                List your cars with us
              </Link>
            )}
          </li>
        </ul>
      </nav>

      {isSales && (
        <nav className="mt-8 border-t border-line pt-8">
          <p className={heading}>Staff</p>
          <ul className="mt-3">
            <li>
              <Link to="/staff/tickets" className={link}>
                Queue
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
            <Button
              variant="secondary"
              size="large"
              className="mt-6 w-full"
              onClick={() => {
                signOut()
                onClose()
              }}
            >
              Sign out
            </Button>
          </>
        ) : (
          <Button
            size="large"
            className="w-full"
            onClick={() => {
              onClose()
              onSignIn()
            }}
          >
            Sign in
          </Button>
        )}
      </div>
    </Modal>
  )
}

export default MobileMenu
