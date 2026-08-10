import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

const queryClient = new QueryClient()

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <queryClient.Provider client={queryClient}>
      <App />
    </queryClient.Provider>
  </StrictMode>,
)
