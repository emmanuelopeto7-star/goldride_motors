import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import CarDetail from './pages/CarDetail'
import LinkedInCallback from './pages/LinkedInCallback'
import NotFound from './pages/NotFound'

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/cars/:id" element={<CarDetail />} />
        <Route path="/auth/linkedin/callback" element={<LinkedInCallback />} />
        {/* Last: * matches whatever no earlier route claimed. */}
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}

export default App
