import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import CarDetail from './pages/CarDetail'


function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/cars/:id" element={<CarDetail />} />
      </Route>
    </Routes>
  )
}

export default App