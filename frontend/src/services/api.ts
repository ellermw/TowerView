import axios from 'axios'
import { useAuthStore } from '../store/authStore'
import toast from 'react-hot-toast'

const API_BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000') + '/api'

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }

  // Log termination requests
  if (config.url?.includes('/terminate')) {
    console.log('TERMINATION REQUEST:', {
      url: config.url,
      method: config.method,
      baseURL: config.baseURL,
      fullURL: `${config.baseURL}${config.url}`
    })
  }

  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      const { refreshToken, logout } = useAuthStore.getState()

      if (refreshToken) {
        try {
          const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
            refresh_token: refreshToken,
          })

          const { access_token, refresh_token } = response.data
          const user = useAuthStore.getState().user

          if (user) {
            useAuthStore.getState().setAuth(user, access_token, refresh_token)
            originalRequest.headers.Authorization = `Bearer ${access_token}`
            return api(originalRequest)
          }
        } catch (refreshError) {
          logout()
          toast.error('Session expired. Please log in again.')
          return Promise.reject(refreshError)
        }
      } else {
        logout()
        toast.error('Session expired. Please log in again.')
      }
    }

    return Promise.reject(error)
  }
)

export default api