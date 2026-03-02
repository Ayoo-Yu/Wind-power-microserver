// src/router/index.js
import { createRouter, createWebHistory } from 'vue-router'
import HomePage from '../components/HomePage.vue' // 主页组件
import AppLayout from '../components/AppLayout.vue' // 布局组件
import AutoPredict  from '../components/AutoPredict.vue'
import PowerCompare from '../components/PowerCompare.vue'
import Login from '../components/Login.vue' // 登录组件
import UserManagement from '../components/UserManagement.vue' // 用户管理组件
import PhysicalSimulation from '../components/PhysicalSimulation.vue' // 物理仿真组件
import SystemMaintenance from '../components/SystemMaintenance.vue' // 系统维护组件
import ReportManagement from '../components/ReportManagement.vue' // 上报管理组件
import WeatherDataFetcher from '../components/WeatherDataFetcher.vue' // 气象数据拉取组件

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    component: AppLayout, // 使用布局组件作为基础
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'HomePage',
        component: HomePage
      },
      {
        path: 'modeltrain',
        name: 'ModelTrain',
        redirect: { name: 'AutoPredict' }
      },
      {
        path: 'powerpredict',
        name: 'PowerPredict',
        redirect: { name: 'AutoPredict' }
      },
      {
        path: 'autopredict',
        name: 'AutoPredict',
        component: AutoPredict,
        meta: { requiredPermissions: ['auto_predictions'] }
      },
      {
        path: 'powercompare',
        name: 'PowerCompare',
        component: PowerCompare,
        meta: { requiredPermissions: ['view_all_data'] }
      },
      {
        path: 'users',
        name: 'UserManagement',
        component: UserManagement,
        meta: { requiredPermissions: ['manage_users'] }
      },
      {
        path: 'physicalsimulation',
        name: 'PhysicalSimulation',
        component: PhysicalSimulation,
        meta: { requiredPermissions: ['run_simulations'] }
      },
      {
        path: 'systemmaintenance',
        name: 'SystemMaintenance',
        component: SystemMaintenance,
        meta: { requiredPermissions: ['system_maintenance'] }
      },
      {
        path: 'reportmanagement',
        name: 'ReportManagement',
        component: ReportManagement,
        meta: { requiredPermissions: ['manage_reports'] }
      },
      {
        path: 'weatherdatafetcher',
        name: 'WeatherDataFetcher',
        component: WeatherDataFetcher,
        meta: { requiredPermissions: ['manage_weather_data'] }
      }
    ]
  },
  // 其他独立路由（如果有）
]

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const userInfo = localStorage.getItem('user')
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth)
  
  // 如果需要认证但没有用户信息，重定向到登录页
  if (requiresAuth && !userInfo) {
    next({ name: 'Login' })
  } 
  // 如果已经有用户信息但访问登录页，重定向到首页
  else if (userInfo && to.name === 'Login') {
    next({ name: 'HomePage' })
  }
  // 其他情况正常导航
  else {
    next()
  }
})

export default router
