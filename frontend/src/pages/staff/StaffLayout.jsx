import { Link, NavLink, Outlet } from 'react-router-dom'
import Button from '../../components/Button'
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
  // Manager and owner only, matching the endpoint behind it. A tab that
  // leads to a 403 is the same mistake as a control with no endpoint.
  ['/staff/overview', 'Overview', true],
  // One queue where there were two. Approvals and Sourcing are kinds of
  // ticket now, not screens of their own.
  ['/staff/tickets', 'Queue'],
  ['/staff/inventory', 'Inventory'],
  ['/staff/orders', 'Orders'],
  ['/staff/payments', 'Payments'],
  ['/staff/enquiries', 'Enquiries'],
  ['/staff/chats', 'Chats'],
  ['/staff/dealers', 'Dealers'],
  ['/staff/settings', 'Settings'],
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
            <Button variant="pill" onClick={signOut} className="border-line">
              Sign out
            </Button>
          </div>
        </div>
      </header>

      <Page>
        <h1 className="font-serif text-h1">Staff</h1>

        <nav className="mt-8 flex flex-wrap gap-6 border-b border-line">
          {TABS.filter(([, , managerOnly]) => !managerOnly || isManager).map(([to, label]) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                // pt-3 as well as pb-3: the tab was a 13px label with 12px
                // under it and nothing above, which is a 34px target on a
                // touchscreen. The rule underneath does not move - pb-3 still
                // sets the distance to it.
                `-mb-px border-b-2 pt-3 pb-3 text-meta transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-current ${
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
