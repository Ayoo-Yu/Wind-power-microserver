import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import './element-variables.scss'
import './assets/main.css'
import './assets/theme.css'
import './assets/form-override.css'
import axios from './api/axios'

const app = createApp(App)
app.config.warnHandler = () => {}
app.use(router)
app.use(ElementPlus)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.config.globalProperties.$axios = axios
app.mount('#app')
