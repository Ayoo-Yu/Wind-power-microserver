import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './assets/main.css'
import './assets/theme.css'
import './assets/form-override.css'
import axios from './api/axios'

const app = createApp(App)
app.config.warnHandler = () => {}

const debounce = (fn, delay) => {
  let timer
  return function () {
    clearTimeout(timer)
    timer = setTimeout(() => fn.apply(this, arguments), delay)
  }
}

const _ResizeObserver = window.ResizeObserver
window.ResizeObserver = class ResizeObserver extends _ResizeObserver {
  constructor(callback) {
    super(debounce(callback, 16))
  }
}

const _origError = console.error
console.error = (...args) => {
  if (args[0] && typeof args[0] === 'string' && args[0].includes('ResizeObserver')) return
  _origError.apply(console, args)
}

app.use(router)
app.use(ElementPlus)

app.config.globalProperties.$axios = axios
app.mount('#app')
