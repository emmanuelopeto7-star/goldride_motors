import axios from 'axios'
import { getToken, clearToken } from '../lib/auth'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
})

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Token ${token}`
  }
  return config
})
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // The key is dead; keeping it would break every public page too.
      clearToken()
    }
    return Promise.reject(error)
  },
)

export default api
