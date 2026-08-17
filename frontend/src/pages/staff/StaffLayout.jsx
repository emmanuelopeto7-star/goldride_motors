import { Link, NavLink, Outlet } from 'react-router-dom'
import Page from '../../components/Page'
import { useAuth } from '../../context/AuthContext'

/** The dashboard shell.
 *
 *  Deliberately outside the storefront <Layout>: the hero-aware header, search
 *  pill, brand strip and footer are all shopfront furniture, and none of them
 *  belong over a work queue. The design rules are unchanged though - §4.1 for
 *  the header, §2.1 for the active tab, §3 geometry throughout.
 *
 *  Tabs are added as their screens land. §"never ship a control whose endpoint
 *  does not exist" applies just as much to a nav item pointing at nothing.
 */

const TABS = [
  ['/staff/approvals', 'Approvals'],
  ['/staff/sourcing', 'Sourcing'],
  ['/staff/inventory', 'Inventory'],
]

function StaffLayout() {
  const { user, isManager, signOut } = useAuth()

  return (
    <div className="min-h-screen bg-page text-ink">
      <header className="sticky top-0 z-50 w-full border-b border-line bg-surface">
        <div className="flex h-[72px] w-full items-center gap-6 px-5 lg:px-12">
          <Link to="/" className="shrink-0 font-serif text-[22px] tracking-[0.08em]">
            GOLDRIDE
          </Link>
          <span className="rounded-full border border-line px-3 py-1 text-badge uppercase text-ink-soft">
            Staff
          </span>

          <div className="ml-auto flex shrink-0 items-center gap-6">
            <span className="hidden text-meta text-ink-soft lg:block">
              {user?.username}
              {/* Which role you hold decides what you can do here, so it is
                  worth stating rather than leaving to be discovered from a
                  greyed-out button. */}
              {isManager ? ' · Manager' : ' · Sales'}
            </span>
            <button
              type="button"
              onClick={signOut}
              className="flex h-10 shrink-0 items-center rounded-full border border-line px-5 text-meta"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <Page>
        <h1 className="font-serif text-h1">Staff</h1>

        <nav className="mt-8 flex flex-wrap gap-6 border-b border-line">
          {TABS.map(([to, label]) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `-mb-px border-b-2 pb-3 text-meta transition-colors ${
                  isActive
                    ? 'border-ink text-ink'
                    : 'border-transparent text-ink-soft hover:text-ink'
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-12">
          <Outlet />
        </div>
      </Page>
    </div>
  )
}

export default StaffLayout
