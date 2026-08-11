import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import api from '../api/client'
import { setToken } from '../lib/auth'
import { errorMessages } from '../lib/errors'

/** Where LinkedIn sends the browser back. Swaps the authorisation code for a
 *  token, then gets out of the way. */
function LinkedInCallback() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [error, setError] = useState(null)
  const ran = useRef(false)

  useEffect(() => {
    // StrictMode runs effects twice in development; an authorisation code is
    // single-use, so the second attempt would always fail.
    if (ran.current) return
    ran.current = true

    const code = searchParams.get('code')
    const state = searchParams.get('state')
    const expected = sessionStorage.getItem('linkedin_state')
    sessionStorage.removeItem('linkedin_state')

    if (searchParams.get('error')) {
      setError('LinkedIn sign-in was cancelled.')
      return
    }

    if (!code || !state || state !== expected) {
      // Either we never started this flow, or someone else did.
      setError('That sign-in link is not valid. Please try again.')
      return
    }

    api
      .post('/api/auth/social/linkedin/', { code })
      .then((res) => {
        setToken(res.data.token)
        navigate('/', { replace: true })
      })
      .catch((err) => setError(errorMessages(err)[0]))
  }, [navigate, searchParams])

  return (
    <div className="mx-auto max-w-[440px] px-5 py-24 text-center">
      {error ? (
        <>
          <p className="font-serif text-section">Sign-in failed</p>
          <p className="mt-3 text-model text-ink-soft">{error}</p>
          <button
            type="button"
            onClick={() => navigate('/', { replace: true })}
            className="mt-8 h-12 border border-ink px-8 text-badge uppercase"
          >
            Back to all cars
          </button>
        </>
      ) : (
        <p className="text-model text-ink-soft">Signing you in…</p>
      )}
    </div>
  )
}

export default LinkedInCallback
