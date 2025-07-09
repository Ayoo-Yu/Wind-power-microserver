// src/main.js
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css' // 确保路径正确
import * as ElementPlusIconsVue from '@element-plus/icons-vue' // 导入Element Plus图标
import './element-variables.scss'
import './assets/main.css'  // 已有的主CSS文件
import './assets/form-override.css'  // 导入新的表单覆盖CSS（放在最后确保优先级最高）
import axios from './api/axios'  // 使用我们配置好的axios实例

// 不再需要重复配置axios，因为已经在api/axios.js中配置过了

const app = createApp(App)
app.config.warnHandler = () => {}
app.use(router)
app.use(ElementPlus)

// 全局注册Element Plus图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 全局挂载axios以便于访问
app.config.globalProperties.$axios = axios

app.mount('#app')
