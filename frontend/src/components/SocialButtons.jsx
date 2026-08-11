import { useEffect, useRef } from 'react'
import { useMutation } from '@tanstack/react-query'
import api from '../api/client'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID
const LINKEDIN_CLIENT_ID = import.meta.env.VITE_LINKEDIN_CLIENT_ID
const LINKEDIN_REDIRECT_URI = import.meta.env.VITE_LINKEDIN_REDIRECT_URI

/** Google and LinkedIn sign-in. A provider with no client id renders nothing -
 *  a button that cannot work is worse than no button. */
function SocialButtons({ onSignedIn, onError }) {
  const googleSlot = useRef(null)

  const social = useMutation({
    mutationFn: async ({ provider, payload }) => {
      const res = await api.post(`/api/auth/social/${provider}/`, payload)
      return res.data
    },
    onSuccess: (data) => onSignedIn(data.token),
    onError: (error) => onError?.(error),
  })

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID || !window.google || !googleSlot.current) return

    window.google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: (response) => {
        // response.credential is the ID token the backend verifies.
        social.mutate({
          provider: 'google',
          payload: { credential: response.credential },
        })
      },
    })

    window.google.accounts.id.renderButton(googleSlot.current, {
      theme: 'outline',
      size: 'large',
      width: 340,
      text: 'continue_with',
    })
    // Runs once: re-initialising Google's client on every render re-mounts
    // its iframe and loses the callback.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function startLinkedIn() {
    // A random state, kept for the callback to compare. Without it, an
    // attacker can feed you their own authorisation code and log you into
    // their account.
    const state = crypto.randomUUID()
    sessionStorage.setItem('linkedin_state', state)

    const url = new URL('https://www.linkedin.com/oauth/v2/authorization')
    url.searchParams.set('response_type', 'code')
    url.searchParams.set('client_id', LINKEDIN_CLIENT_ID)
    url.searchParams.set('redirect_uri', LINKEDIN_REDIRECT_URI)
    url.searchParams.set('scope', 'openid profile email')
    url.searchParams.set('state', state)

    window.location.href = url.toString()
  }

  const hasGoogle = Boolean(GOOGLE_CLIENT_ID)
  const hasLinkedIn = Boolean(LINKEDIN_CLIENT_ID && LINKEDIN_REDIRECT_URI)

  if (!hasGoogle && !hasLinkedIn) return null

  return (
    <div className="space-y-3">
      {hasGoogle && <div ref={googleSlot} className="flex justify-center" />}

      {hasLinkedIn && (
        <button
          type="button"
          onClick={startLinkedIn}
          disabled={social.isPending}
          className="flex h-12 w-full items-center justify-center gap-3 border border-line bg-surface text-model disabled:opacity-50"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
            <path
              fill="#0A66C2"
              d="M20.45 20.45h-3.56v-5.57c0-1.33-.02-3.04-1.85-3.04-1.85 0-2.14 1.45-2.14 2.94v5.67H9.35V9h3.41v1.56h.05a3.74 3.74 0 0 1 3.37-1.85c3.6 0 4.27 2.37 4.27 5.46zM5.34 7.43a2.06 2.06 0 1 1 0-4.13 2.06 2.06 0 0 1 0 4.13M7.12 20.45H3.55V9h3.57zM22.22 0H1.77C.79 0 0 .77 0 1.72v20.55C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.73V1.72C24 .77 23.2 0 22.22 0"
            />
          </svg>
          Continue with LinkedIn
        </button>
      )}

      <div className="flex items-center gap-4">
        <span className="h-px flex-1 bg-line" />
        <span className="text-meta text-ink-mute">OR</span>
        <span className="h-px flex-1 bg-line" />
      </div>
    </div>
  )
}

export default SocialButtons
