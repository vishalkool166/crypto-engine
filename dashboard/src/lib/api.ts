import axios from 'axios'

// Production APIs share the application origin. Vite proxies API paths in development.
const BASE_URL = ''

export const api = axios.create({
  baseURL:         BASE_URL,
  withCredentials: true,
  timeout:         30000,
  headers:         { 'Content-Type': 'application/json' },
})

export const authApi = axios.create({
  baseURL:         BASE_URL,
  withCredentials: true,
  timeout:         30000,
  headers:         { 'Content-Type': 'application/json' },
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const url           = error.config?.url ?? ''
      const isAuthRoute   = url.includes('/auth/')
      const isLoginPage   = window.location.pathname === '/login'
      if (!isAuthRoute && !isLoginPage) {
        import('@/stores/authStore').then(({ useAuthStore }) => {
          useAuthStore.getState().logout()
        })
        window.location.href = '/welcome'
      }
    }
    return Promise.reject(error)
  }
)

export default api
