import { Link, Outlet } from 'react-router-dom'
import Button from '../../components/Button'
import Page from '../../components/Page'
import { useAuth } from '../../context/AuthContext'
import { useDealerProfile } from '../../hooks/useDealer'

/** The dealer portal shell.
 *
 *  Outside the storefront <Layout> for the same reason the staff dashboard is:
 *  the hero-aware header, search pill and brand strip are shopfront furniture,
 *  and none of it belongs over somebody's own stock list. One tab today, so
 *  there is no nav row - a single tab is a label pretending to be a choice.
 */
function DealerLayout() {
  const { signOut } = useAuth()
  const { data: dealer } = useDealerProfile()

  return (
    <div className="min-h-screen bg-page">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-20 max-w-[1440px] items-center gap-8 px-5 lg:px-12">
          <Link to="/" className="shrink-0 font-serif text-[22px] tracking-[0.08em]">
            GOLDRIDE
          </Link>
          <span className="text-badge uppercase tracking-[0.08em] text-ink-mute">
            Dealer
          </span>

          <div className="ml-auto flex items-center gap-6">
            <span className="hidden text-meta text-ink-soft sm:inline">
              {dealer?.name ?? ''}
            </span>
            <Button variant="quiet" onClick={signOut}>
              Sign out
            </Button>
          </div>
        </div>
      </header>

      <Page>
        <Outlet />
      </Page>
    </div>
  )
}

export default DealerLayout
