import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'
import { isAuthReady, isAuthLoading } from '../store/authReady'

// --- Database maintenance state (shared across app) ---
export const dbState = {
  unavailable: false,
  _timer: null,
  _listeners: [],

  setUnavailable() {
    if (this.unavailable) return
    this.unavailable = true
    this._notify()
    ElMessage({ message: '数据库维护中，部分功能暂不可用', type: 'warning', duration: 5000 })
  },

  setAvailable() {
    if (!this.unavailable) return
    this.unavailable = false
    clearTimeout(this._timer)
    this._notify()
    ElMessage({ message: '数据库已恢复连接', type: 'success', duration: 3000 })
  },

  onChange(fn) {
    this._listeners.push(fn)
    return () => { this._listeners = this._listeners.filter(l => l !== fn) }
  },

  _notify() {
    this._listeners.forEach(fn => fn(this.unavailable))
  }
}

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
    const silent = error.config?._silent
    const status = error.response?.status

    if (!silent) {
      console.warn('Response error:', error.message, status ? `(HTTP ${status})` : '')
    }

    if (error.response) {
      // 503 = database temporarily unavailable
      if (status === 503) {
        const body = error.response.data
        if (body?.error === 'database_temporarily_unavailable') {
          dbState.setUnavailable()
          clearTimeout(dbState._timer)
          const pollHealth = () => {
            dbState._timer = setTimeout(() => {
              instance.get('/health', { _silent: true }).then(resp => {
                if (resp.data?.database === 'ok') dbState.setAvailable()
                else pollHealth()
              }).catch(() => { pollHealth() })
            }, 30000)
          }
          pollHealth()
          error._dbUnavailable = true
          return Promise.reject(error)
        }
      }

      // If we get any successful response, clear DB unavailable state
      if (status < 500) {
        dbState.setAvailable()
      }

      if (status === 401) {
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
    } else if (error.request && !silent) {
      console.warn('No response received for:', error.config?.url)
    }

    // For 5xx server errors, suppress toast but still reject so callers
    // (including withLegacyFallback) can handle the error properly.
    // Attach a marker so callers know this was a server error.
    if (status >= 500 && status < 600) {
      error._serverError = true
      return Promise.reject(error)
    }

    // Suppress error toasts for requests that opt out via _silent config
    if (!silent) {
      if (error.message === 'Network Error') {
        ElMessage.error('网络错误，请检查您的网络连接或服务状态')
      } else if (!error.response || status !== 401) {
        ElMessage.error(error.response?.data?.message || '请求失败')
      }
    }

    return Promise.reject(error)
  }
)

export default instance
