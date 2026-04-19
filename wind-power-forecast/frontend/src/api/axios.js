import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'
import { isAuthReady, isAuthLoading } from '../store/authReady'

// All API requests use relative paths so dev proxy and production Nginx keep the same contracts.
const API_BASE_URL = '/'


const instance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  withCredentials: false,
  headers: {
    'Content-Type': 'application/json'
  }
})

instance.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('accessToken')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    return config
  },
  (error) => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

instance.interceptors.response.use(
  (response) => {
    return response
  },
  (error) => {
    console.error('Response error:', error.message)

    if (error.response) {
      console.error('Status code:', error.response.status)
      console.error('Response data:', error.response.data)
      console.error('Request URL:', error.config?.url)

      if (error.response.status === 401) {
        console.warn('Authentication failed or token expired:', error.config?.url)

        localStorage.removeItem('accessToken')
        localStorage.removeItem('user')

        isAuthReady.value = false
        isAuthLoading.value = false

        const isOnLoginPage = router.currentRoute.value.path === '/login'
        if (!isOnLoginPage) {
          ElMessage.error('您的登录已过期，请重新登录')
          router.push('/login')
        }
      }
    } else if (error.request) {
      console.error('Request was sent but no response was received')
      console.error('Request details:', error.request)
    }

    // Suppress error toasts for requests that opt out via _silent config
    const silent = error.config?._silent
    if (!silent) {
      if (error.message === 'Network Error') {
        ElMessage.error('网络错误，请检查您的网络连接或服务状态')
      } else if (!error.response || error.response.status !== 401) {
        ElMessage.error(error.response?.data?.message || '请求失败')
      }
    }

    return Promise.reject(error)
  }
)

export default instance
