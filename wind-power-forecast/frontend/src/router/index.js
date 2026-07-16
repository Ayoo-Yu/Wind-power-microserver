import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getStoredUser, hasAnyPermission } from '../utils/permission'
const HomePage = () => import('../components/HomePage.vue')
const AppLayout = () => import('../components/AppLayout.vue')
const AutoPredict = () => import('../components/AutoPredict.vue')
const PowerCompare = () => import('../components/PowerCompare.vue')
const AccuracyReport = () => import('../components/AccuracyReport.vue')
const Login = () => import('../components/Login.vue')
const AccessManagement = () => import('../components/AccessManagement.vue')
const AuditLog = () => import('../components/AuditLog.vue')
const AlarmCenter = () => import('../components/AlarmCenter.vue')
const DataQualityManagement = () => import('../components/DataQualityManagement.vue')
const ManualInterventionWorkspace = () => import('../components/ManualInterventionWorkspace.vue')
const SystemSettings = () => import('../components/SystemSettings.vue')
const ReportManagement = () => import('../components/ReportManagement.vue')
const WeatherDataFetcher = () => import('../components/WeatherDataFetcher.vue')
const FarmManagement = () => import('../components/FarmManagement.vue')
const PowerCurveAnalysis = () => import('../components/PowerCurveAnalysis.vue')
const ScadaConnection = () => import('../components/ScadaConnection.vue')
const DataPopulation = () => import('../views/DataPopulation.vue')
const DatabaseGovernance = () => import('../components/DatabaseGovernance.vue')
const OperationsCenter = () => import('../components/OperationsCenter.vue')

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
        component: HomePage,
        meta: { title: '首页总览', keepAlive: true, affix: true }
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
        meta: { title: '预测任务', requiredPermissions: ['auto_predictions'], keepAlive: true }
      },
      {
        path: 'manual-workspace',
        name: 'ManualInterventionWorkspace',
        component: ManualInterventionWorkspace,
        meta: { title: '人工修正', requiredPermissions: ['manual_intervention_workspace', 'auto_predictions'], keepAlive: true }
      },
      {
        path: 'powercompare',
        name: 'PowerCompare',
        component: PowerCompare,
        meta: { title: '预测曲线与考核', requiredPermissions: ['view_all_data'], keepAlive: true }
      },
      {
        path: 'accuracy-report',
        name: 'AccuracyReport',
        component: AccuracyReport,
        meta: { title: '月度准确率报表', requiredPermissions: ['view_accuracy_report', 'view_all_data'], keepAlive: true }
      },
      {
        path: 'reportmanagement',
        name: 'ReportManagement',
        component: ReportManagement,
        meta: { title: '上报配置', requiredPermissions: ['manage_reports'], keepAlive: true }
      },
      {
        path: 'weatherdatafetcher',
        name: 'WeatherDataFetcher',
        component: WeatherDataFetcher,
        meta: { title: '气象数据接入', requiredPermissions: ['manage_weather_data'], keepAlive: true }
      },
      {
        path: 'data-population',
        name: 'DataPopulation',
        component: DataPopulation,
        meta: { title: '历史数据补齐', requiredPermissions: ['manage_data_import'], keepAlive: true }
      },
      {
        path: 'farmmanagement',
        name: 'FarmManagement',
        component: FarmManagement,
        meta: { title: '场站配置', requiredPermissions: ['manage_reports'], keepAlive: true }
      },
      {
        path: 'power-curve',
        name: 'PowerCurveAnalysis',
        component: PowerCurveAnalysis,
        meta: { title: '风速功率曲线', requiredPermissions: ['view_all_data'], keepAlive: true }
      },
      {
        path: 'scada-connections',
        name: 'ScadaConnection',
        component: ScadaConnection,
        meta: { title: 'SCADA数据源', requiredPermissions: ['manage_system_settings'], keepAlive: true }
      },
      {
        path: 'operations-center',
        name: 'OperationsCenter',
        component: OperationsCenter,
        meta: { title: '链路运行状态', requiredPermissions: ['view_alarm_center'], keepAlive: true }
      },
      {
        path: 'alarm-center',
        name: 'AlarmCenter',
        component: AlarmCenter,
        meta: { title: '告警处置', requiredPermissions: ['view_alarm_center', 'manage_reports'], keepAlive: true }
      },
      {
        path: 'data-quality',
        name: 'DataQualityManagement',
        component: DataQualityManagement,
        meta: { title: '数据质量与限电', requiredPermissions: ['manage_data_quality', 'view_all_data'], keepAlive: true }
      },
      {
        path: 'users',
        name: 'UserManagement',
        component: AccessManagement,
        meta: { title: '账号与权限', requiredPermissions: ['manage_users', 'manage_roles'], keepAlive: true }
      },
      {
        path: 'users/roles',
        name: 'RoleManagement',
        redirect: { path: '/users', query: { tab: 'roles' } },
        meta: { requiredPermissions: ['manage_roles'] }
      },
      {
        path: 'users/audit-logs',
        name: 'AuditLog',
        component: AuditLog,
        meta: { title: '操作日志审计', requiredPermissions: ['view_audit_logs', 'manage_users'], keepAlive: true }
      },
      {
        path: 'system-settings',
        name: 'SystemSettings',
        component: SystemSettings,
        meta: { title: '系统基础配置', requiredPermissions: ['manage_system_settings', 'system_maintenance'], keepAlive: true }
      },
      {
        path: 'database-governance',
        name: 'DatabaseGovernance',
        component: DatabaseGovernance,
        meta: { title: '数据库治理', requiredPermissions: ['system_maintenance'], keepAlive: true }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

router.beforeEach((to, from, next) => {
  const user = getStoredUser()
  const userInfo = !!user
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth)
  const requiredPermissions = to.matched.flatMap(record => record.meta?.requiredPermissions || [])

  if (requiresAuth && !userInfo) {
    next({ name: 'Login' })
  } else if (userInfo && to.name === 'Login') {
    next({ name: 'HomePage' })
  } else if (userInfo && !hasAnyPermission(user, requiredPermissions)) {
    ElMessage.warning('当前账号没有访问该页面的权限')
    next({ name: 'HomePage' })
  } else {
    next()
  }
})

export default router
