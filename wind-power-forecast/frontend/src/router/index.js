import { createRouter, createWebHistory } from 'vue-router'
import HomePage from '../components/HomePage.vue'
import AppLayout from '../components/AppLayout.vue'
import AutoPredict from '../components/AutoPredict.vue'
import PowerCompare from '../components/PowerCompare.vue'
import Login from '../components/Login.vue'
import UserManagement from '../components/UserManagement.vue'
import ReportManagement from '../components/ReportManagement.vue'
import WeatherDataFetcher from '../components/WeatherDataFetcher.vue'
import FarmManagement from '../components/FarmManagement.vue'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    component: AppLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'HomePage',
        component: HomePage
      },
      {
        path: 'modeltrain',
        redirect: '/autopredict'
      },
      {
        path: 'powerpredict',
        redirect: '/autopredict'
      },
      {
        path: 'autopredict',
        name: 'AutoPredict',
        component: AutoPredict,
        meta: { requiredPermissions: ['auto_predictions'], keepAlive: true }
      },
      {
        path: 'powercompare',
        name: 'PowerCompare',
        component: PowerCompare,
        meta: { requiredPermissions: ['view_all_data'], keepAlive: true }
      },
      {
        path: 'reportmanagement',
        name: 'ReportManagement',
        component: ReportManagement,
        meta: { requiredPermissions: ['manage_reports'], keepAlive: true }
      },
      {
        path: 'weatherdatafetcher',
        name: 'WeatherDataFetcher',
        component: WeatherDataFetcher,
        meta: { requiredPermissions: ['manage_weather_data'], keepAlive: true }
      },
      {
        path: 'farmmanagement',
        name: 'FarmManagement',
        component: FarmManagement,
        meta: { requiredPermissions: ['manage_reports'], keepAlive: true }
      },
      {
        path: 'users',
        name: 'UserManagement',
        component: UserManagement,
        meta: { requiredPermissions: ['manage_users'], keepAlive: true }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes
})

router.beforeEach((to, from, next) => {
  const userInfo = localStorage.getItem('user')
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth)

  if (requiresAuth && !userInfo) {
    next({ name: 'Login' })
  } else if (userInfo && to.name === 'Login') {
    next({ name: 'HomePage' })
  } else {
    next()
  }
})

export default router
