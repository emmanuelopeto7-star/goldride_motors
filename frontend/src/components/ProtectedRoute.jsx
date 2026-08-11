import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import Page from './Page'

/** Hiding a route is convenience, not security - the API refuses regardless.
 *  `allow` receives the whole auth object, so a route can ask for a role. */
function ProtectedRoute({ children, allow }) {
  const auth = useAuth()

  // Deciding before /api/me/ answers would bounce a signed-in user home.
  if (auth.isLoading) {
    return (
      <Page>
        <div className="h-64 w-full max-w-[560px] animate-pulse bg-line" />
      </Page>
    )
  }

  if (!auth.user) return <Navigate to="/" replace />
  if (allow && !allow(auth)) return <Navigate to="/" replace />

  return children
}

export default ProtectedRoute
