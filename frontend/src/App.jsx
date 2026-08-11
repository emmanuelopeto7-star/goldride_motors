import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import CarDetail from './pages/CarDetail'
import LinkedInCallback from './pages/LinkedInCallback'

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/cars/:id" element={<CarDetail />} />
        <Route path="/auth/linkedin/callback" element={<LinkedInCallback />} />
      </Route>
    </Routes>
  )
}

export default App
