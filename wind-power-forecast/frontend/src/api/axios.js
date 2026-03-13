import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'
import { isAuthReady, isAuthLoading } from '../store/authReady'

// In local development, send requests to relative `/api...` paths so the Vue
// dev server proxy forwards them to the backend on 18080/18081. In deployed
// environments, keep using the same host via the reverse proxy entrypoint.
let API_BASE_URL = '/'

if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
  API_BASE_URL = `http://${window.location.hostname}:8080`
}

console.log('Using API base URL:', API_BASE_URL)

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
    console.log('Sending request:', config.method?.toUpperCase(), config.url)

    const token = localStorage.getItem('accessToken')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
      console.log('Attached auth token to request:', config.url)
    } else {
      console.warn('Request sent without auth token:', config.url)
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
    console.log('Received response:', response.status, response.config.url)
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

        ElMessage.error('您的登录已过期，请重新登录')

        if (router.currentRoute.value.path !== '/login') {
          router.push('/login')
        }
      }
    } else if (error.request) {
      console.error('Request was sent but no response was received')
      console.error('Request details:', error.request)
    }

    if (error.message === 'Network Error') {
      ElMessage.error('网络错误，请检查您的网络连接或服务状态')
    } else if (!error.response || error.response.status !== 401) {
      ElMessage.error(error.response?.data?.message || '请求失败')
    }

    return Promise.reject(error)
  }
)

export default instance
