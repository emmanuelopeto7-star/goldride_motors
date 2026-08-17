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
import StaffApprovals from './pages/staff/StaffApprovals'
import StaffLayout from './pages/staff/StaffLayout'

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
        <Route index element={<Navigate to="/staff/approvals" replace />} />
        <Route path="approvals" element={<StaffApprovals />} />
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
