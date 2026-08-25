import { Navigate, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import AccountLayout from './pages/AccountLayout'
import Home from './pages/Home'
import ImportRequest from './pages/ImportRequest'
import ImportTracking from './pages/ImportTracking'
import CarDetail from './pages/CarDetail'
import LinkedInCallback from './pages/LinkedInCallback'
import MyEnquiries from './pages/MyEnquiries'
import MyOrders from './pages/MyOrders'
import MyProfile from './pages/MyProfile'
import MyRequests from './pages/MyRequests'
import MySaved from './pages/MySaved'
import NotFound from './pages/NotFound'
import TrackOrder from './pages/TrackOrder'
import StaffEnquiries from './pages/staff/StaffEnquiries'
import StaffInventory from './pages/staff/StaffInventory'
import StaffLayout from './pages/staff/StaffLayout'
import StaffOrders from './pages/staff/StaffOrders'
import StaffPayments from './pages/staff/StaffPayments'
import StaffSettings from './pages/staff/StaffSettings'
import StaffTicketDetail from './pages/staff/StaffTicketDetail'
import StaffTickets from './pages/staff/StaffTickets'

function App() {
  return (
    <Routes>
      {/* Outside <Layout> on purpose: the dashboard has its own shell, with
          none of the storefront's hero-aware header, search or footer.
          isSales covers Manager too, and the API re-checks every call. */}
      <Route
        path="/staff"
        element={
          <ProtectedRoute allow={(auth) => auth.isSales}>
            <StaffLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/staff/tickets" replace />} />
        <Route path="tickets" element={<StaffTickets />} />
        <Route path="tickets/:id" element={<StaffTicketDetail />} />
        {/* Tickets replaced these two queues rather than sitting on top of
            them. The paths stay as redirects because they are in people's
            bookmarks and in the browser history of everyone who used the
            dashboard before today. */}
        <Route path="approvals" element={<Navigate to="/staff/tickets?kind=approval" replace />} />
        <Route path="sourcing" element={<Navigate to="/staff/tickets?kind=sourcing" replace />} />
        <Route path="sourcing/:id" element={<Navigate to="/staff/tickets?kind=sourcing" replace />} />
        <Route path="inventory" element={<StaffInventory />} />
        <Route path="orders" element={<StaffOrders />} />
        <Route path="payments" element={<StaffPayments />} />
        <Route path="enquiries" element={<StaffEnquiries />} />
        <Route path="settings" element={<StaffSettings />} />
      </Route>

      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/cars/:id" element={<CarDetail />} />
        <Route path="/auth/linkedin/callback" element={<LinkedInCallback />} />
        {/* Public: the UUID is the credential, so no guard here. */}
        <Route path="/track/:token" element={<TrackOrder />} />
        <Route path="/import" element={<ImportRequest />} />
        <Route path="/imports/:token" element={<ImportTracking />} />

        {/* One guard for the whole account area, one shell for its tabs. */}
        <Route
          path="/my"
          element={
            <ProtectedRoute>
              <AccountLayout />
            </ProtectedRoute>
          }
        >
          <Route path="orders" element={<MyOrders />} />
          <Route path="requests" element={<MyRequests />} />
          <Route path="saved" element={<MySaved />} />
          <Route path="enquiries" element={<MyEnquiries />} />
          <Route path="profile" element={<MyProfile />} />
        </Route>

        {/* Last: * matches whatever no earlier route claimed. */}
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}

export default App
