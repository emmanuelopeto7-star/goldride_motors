import { NavLink, Outlet } from 'react-router-dom'
import Page from '../components/Page'

const TABS = [
  ['/my/orders', 'Orders'],
  ['/my/requests', 'Requests'],
  ['/my/saved', 'Saved'],
  ['/my/enquiries', 'Enquiries'],
  ['/my/profile', 'Profile'],
]

function AccountLayout() {
  return (
    <Page>
      <h1 className="font-serif text-h1">My account</h1>

      <nav className="mt-8 flex flex-wrap gap-6 border-b border-line">
        {TABS.map(([to, label]) => (
          <NavLink
            key={to}
            to={to}
            // §2.1: the active state is black and underlined, never coloured.
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
  )
}

export default AccountLayout
