<template>
  <el-container class="app-container">
    <div v-if="isAuthLoading" class="auth-loading-overlay">
      <div class="auth-loading-container">
        <el-icon class="loading-icon"><Loading /></el-icon>
        <div class="auth-loading-text">认证状态检查中...</div>
      </div>
    </div>

    <div class="background-container">
      <div :style="backgroundStyle"></div>
    </div>

    <el-aside :width="isCollapsed ? '64px' : '240px'" class="sidebar">
      <div class="brand" @click="toggleCollapse">
        <img v-if="!isCollapsed" src="@/assets/Sanxia_logo.png" alt="Logo" class="brand-logo" />
        <el-icon v-else class="collapse-icon"><Expand /></el-icon>
      </div>

      <el-menu :default-active="activeMenu" class="el-menu-vertical" :collapse="isCollapsed" @select="handleSelect">
        <el-menu-item index="/">
          <el-icon><HomeFilled /></el-icon>
          <template #title>首页大屏</template>
        </el-menu-item>

        <el-sub-menu index="/group-predict" v-if="hasPermission('auto_predictions') || hasPermission('manual_intervention_workspace')">
          <template #title>
            <el-icon><Timer /></el-icon>
            <span>预测与控制</span>
          </template>
          <el-menu-item index="/autopredict" v-if="hasPermission('auto_predictions')">状态监控</el-menu-item>
          <el-menu-item index="/manual-workspace" v-if="hasPermission('manual_intervention_workspace') || hasPermission('auto_predictions')">
            人工修正工作台
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="/group-analysis" v-if="hasPermission('view_all_data') || hasPermission('view_accuracy_report')">
          <template #title>
            <el-icon><DataAnalysis /></el-icon>
            <span>分析与报表</span>
          </template>
          <el-menu-item index="/powercompare" v-if="hasPermission('view_all_data')">功率可视化对比</el-menu-item>
          <el-menu-item index="/accuracy-report" v-if="hasPermission('view_accuracy_report') || hasPermission('view_all_data')">
            准确率/合格率报表
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="/group-exchange" v-if="hasPermission('manage_weather_data') || hasPermission('manage_reports')">
          <template #title>
            <el-icon><Upload /></el-icon>
            <span>数据交互</span>
          </template>
          <el-menu-item index="/weatherdatafetcher" v-if="hasPermission('manage_weather_data')">气象数据拉取</el-menu-item>
          <el-menu-item index="/reportmanagement" v-if="hasPermission('manage_reports')">上报配置与调度</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="/group-ops" v-if="hasPermission('view_alarm_center') || hasPermission('manage_data_quality') || hasPermission('manage_reports')">
          <template #title>
            <el-icon><WarnTriangleFilled /></el-icon>
            <span>运维与质量</span>
          </template>
          <el-menu-item index="/alarm-center" v-if="hasPermission('view_alarm_center') || hasPermission('manage_reports')">统一告警中心</el-menu-item>
          <el-menu-item index="/data-quality" v-if="hasPermission('manage_data_quality') || hasPermission('view_all_data')">
            数据质量与限电标记
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu
          index="/group-admin"
          v-if="hasPermission('manage_reports') || hasPermission('manage_users') || hasPermission('manage_roles') || hasPermission('manage_system_settings')"
        >
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>系统管理</span>
          </template>
          <el-menu-item index="/farmmanagement" v-if="hasPermission('manage_reports')">场站管理</el-menu-item>
          <el-menu-item index="/users" v-if="hasPermission('manage_users')">用户列表</el-menu-item>
          <el-menu-item index="/users/roles" v-if="hasPermission('manage_roles')">用户与权限</el-menu-item>
          <el-menu-item index="/system-settings" v-if="hasPermission('manage_system_settings') || hasPermission('system_maintenance')">
            系统基础配置
          </el-menu-item>
          <el-menu-item index="/users/audit-logs" v-if="hasPermission('manage_users') || hasPermission('view_audit_logs')">
            操作日志审计
          </el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>

    <el-container class="main-container">
      <el-header class="header">
        <div class="header-left">
          <el-icon class="collapse-btn" @click="toggleCollapse">
            <Fold v-if="!isCollapsed" />
            <Expand v-else />
          </el-icon>
          <h1 class="header-title">{{ uiText.platformTitle }}</h1>
        </div>

        <div class="header-right">
          <el-badge :value="alertCount" :max="99" class="alert-badge">
            <el-button class="alert-btn" text @click="goAlerts">
              <el-icon><Bell /></el-icon>
            </el-button>
          </el-badge>

          <div class="system-time-chip">
            <span class="time-dot"></span>
            <span class="time-label">{{ uiText.updatedLabel }}</span>
            <span class="time-value">{{ systemTime }}</span>
          </div>

          <FarmSelector @farm-changed="handleFarmChanged" />

          <el-dropdown @command="handleCommand">
            <span class="user-profile">
              <el-avatar :size="32" class="avatar">{{ userInitial }}</el-avatar>
              <span class="username">{{ userName }}</span>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main-content">
        <router-view v-slot="{ Component, route: currentRoute }">
          <keep-alive :include="keepAliveRouteNames">
            <component :is="Component" :key="currentRoute.name || currentRoute.path" />
          </keep-alive>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script>
import { ref, computed, provide, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getCurrentUser } from '../api/auth'
import { isAuthReady, isAuthLoading } from '../store/authReady'
import { UI_TEXT } from '../constants/uiText'
import {
  HomeFilled,
  Fold,
  Expand,
  Timer,
  User,
  Loading,
  Upload,
  Histogram,
  Cloudy,
  OfficeBuilding,
  DataAnalysis,
  WarnTriangleFilled,
  Setting,
  Bell
} from '@element-plus/icons-vue'
import FarmSelector from './FarmSelector.vue'
import farmService from '../utils/farmService'

export default {
  name: 'AppLayout',
  components: {
    HomeFilled,
    Fold,
    Expand,
    Timer,
    User,
    Loading,
    Upload,
    Histogram,
    Cloudy,
    OfficeBuilding,
    DataAnalysis,
    WarnTriangleFilled,
    Setting,
    Bell,
    FarmSelector
  },
  setup() {
    const router = useRouter()
    const route = useRoute()

    const isCollapsed = ref(false)
    const isAnimatedBackground = ref(true)
    const currentUser = ref(null)
    const uiText = UI_TEXT.appLayout
    const systemTime = ref('')
    const alertCount = ref(0)
    let timeTicker = null

    provide('isAnimatedBackground', isAnimatedBackground)

    const backgroundStyle = computed(() => ({
      position: 'absolute',
      top: '0',
      left: '0',
      width: '100%',
      height: '100%',
      background: 'radial-gradient(circle at 18% 8%, rgba(18, 215, 255, 0.18) 0%, rgba(18, 215, 255, 0) 42%), linear-gradient(140deg, #05111c 0%, #071b2c 58%, #04111d 100%)',
      opacity: '1'
    }))

    const activeMenu = computed(() => (route.path === '/' ? '/' : route.path))
    const keepAliveRouteNames = computed(() =>
      router
        .getRoutes()
        .filter(r => r.meta?.keepAlive && typeof r.name === 'string')
        .map(r => r.name)
    )

    const userInitial = computed(() => {
      const userStr = localStorage.getItem('user')
      if (!userStr) return '用户'
      const user = JSON.parse(userStr)
      return user.full_name ? user.full_name.charAt(0).toUpperCase() : user.username.charAt(0).toUpperCase()
    })

    const userName = computed(() => {
      const userStr = localStorage.getItem('user')
      if (!userStr) return '用户'
      const user = JSON.parse(userStr)
      return user.full_name || user.username
    })

    const formatDateTime = (date) => {
      const y = date.getFullYear()
      const m = String(date.getMonth() + 1).padStart(2, '0')
      const d = String(date.getDate()).padStart(2, '0')
      const hh = String(date.getHours()).padStart(2, '0')
      const mm = String(date.getMinutes()).padStart(2, '0')
      const ss = String(date.getSeconds()).padStart(2, '0')
      return `${y}-${m}-${d} ${hh}:${mm}:${ss}`
    }

    const refreshSystemTime = () => {
      systemTime.value = formatDateTime(new Date())
    }

    const fetchCurrentUser = async () => {
      isAuthLoading.value = true
      isAuthReady.value = false

      const token = localStorage.getItem('accessToken')
      const userStr = localStorage.getItem('user')

      if (!token || !userStr) {
        isAuthLoading.value = false
        isAuthReady.value = false
        if (router.currentRoute.value.path !== '/login') {
          router.push('/login')
        }
        return
      }

      try {
        currentUser.value = JSON.parse(userStr)
        await getCurrentUser()
        isAuthReady.value = true
      } catch (error) {
        localStorage.removeItem('accessToken')
        localStorage.removeItem('user')
        currentUser.value = null
        isAuthReady.value = false
        if (router.currentRoute.value.path !== '/login') {
          router.push('/login')
        }
      } finally {
        isAuthLoading.value = false
      }
    }

    const hasPermission = (permission) => {
      if (!currentUser.value) return false

      const role = currentUser.value.role
      const roleName = typeof role === 'string' ? role : role?.name
      if (roleName === '系统管理员' || roleName === 'admin' || roleName === 'Administrator') {
        return true
      }

      let permissions = currentUser.value.permissions
      if (permissions && typeof permissions === 'object' && !Array.isArray(permissions) && permissions.permissions) {
        permissions = permissions.permissions
      }

      return Array.isArray(permissions) ? permissions.includes(permission) : false
    }

    provide('hasPermission', hasPermission)

    const toggleCollapse = () => {
      isCollapsed.value = !isCollapsed.value
    }

    const handleSelect = (index) => {
      router.push(index)
    }

    const handleCommand = (command) => {
      if (command === 'logout') {
        handleLogout()
      }
    }

    const handleFarmChanged = (farmCode) => {
      farmService.setCurrentFarm(farmCode)
    }

    const goAlerts = () => {
      router.push('/alarm-center')
    }

    const handleLogout = () => {
      ElMessageBox.confirm('确定要退出登录吗？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      })
        .then(() => {
          localStorage.removeItem('user')
          localStorage.removeItem('accessToken')
          ElMessage.success('已成功退出登录')
          router.push('/login')
        })
        .catch(() => {})
    }

    onMounted(() => {
      refreshSystemTime()
      timeTicker = setInterval(refreshSystemTime, 1000)
      fetchCurrentUser()
    })

    onUnmounted(() => {
      if (timeTicker) {
        clearInterval(timeTicker)
      }
    })

    return {
      isCollapsed,
      activeMenu,
      keepAliveRouteNames,
      toggleCollapse,
      handleSelect,
      backgroundStyle,
      userInitial,
      userName,
      alertCount,
      uiText,
      systemTime,
      goAlerts,
      handleCommand,
      handleFarmChanged,
      hasPermission,
      isAuthReady,
      isAuthLoading
    }
  }
}
</script>

<style scoped>
.app-container {
  height: 100vh;
  position: relative;
}

.background-container {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
}

.main-container,
.sidebar {
  position: relative;
  z-index: 1;
}

.main-container,
.main-content {
  background: transparent !important;
}

.main-content {
  padding: 0;
  overflow-y: auto;
}

.sidebar {
  background: linear-gradient(180deg, #081a2a 0%, #071626 100%);
  border-right: 1px solid rgba(129, 179, 214, 0.24);
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 1000;
  box-shadow: 4px 0 14px rgba(0, 0, 0, 0.22);
}

.brand {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  cursor: pointer;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.brand-logo {
  height: 40px;
}

.collapse-icon {
  font-size: 24px;
  color: #fff;
}

.el-menu-vertical,
.el-menu {
  border-right: none;
  background: transparent;
  border: none;
}

.el-menu-item {
  color: var(--text-secondary);
  height: 50px;
  margin: 8px 0;
}

:deep(.el-sub-menu__title) {
  color: var(--text-secondary);
  height: 50px;
  margin: 8px 0;
}

:deep(.el-sub-menu .el-menu-item) {
  min-width: 0;
  height: 44px;
  margin: 0;
  padding-left: 54px !important;
}

.el-menu-item.is-active {
  background: linear-gradient(90deg, rgba(18, 215, 255, 0.24), rgba(18, 215, 255, 0.04));
  color: #9beaff;
  border-left: 3px solid #12d7ff;
  box-shadow: inset 0 0 0 1px rgba(18, 215, 255, 0.2);
}

.el-menu-item:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #fff;
}

.el-menu-item .el-icon {
  font-size: 20px;
}

.header {
  background: var(--card-dark);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border-color);
  z-index: 999;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 64px;
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.collapse-btn {
  font-size: 20px;
  cursor: pointer;
  color: var(--text-primary);
}

.header-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.alert-badge :deep(.el-badge__content) {
  background: var(--danger);
  border-color: transparent;
}

.alert-btn {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 1px solid rgba(146, 186, 220, 0.35);
  background: rgba(10, 25, 38, 0.6);
  color: var(--text-primary);
}

.system-time-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid rgba(146, 186, 220, 0.35);
  background: rgba(10, 25, 38, 0.6);
  color: var(--text-secondary);
  font-size: 12px;
}

.time-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent-2);
  box-shadow: 0 0 8px rgba(45, 211, 111, 0.75);
}

.time-value {
  color: var(--text-primary);
  font-family: Consolas, 'Roboto Mono', monospace;
}

.user-profile {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 6px 12px;
  border-radius: 20px;
  transition: all 0.3s ease;
  background: rgba(255, 255, 255, 0.05);
}

.user-profile:hover {
  background: rgba(255, 255, 255, 0.1);
}

.username {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.auth-loading-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
}

.auth-loading-container {
  background-color: #fff;
  padding: 30px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  align-items: center;
}

.auth-loading-text {
  margin-top: 15px;
  font-size: 16px;
  color: #333;
}

.loading-icon {
  font-size: 32px;
  color: #409eff;
  animation: rotating 2s linear infinite;
}

@keyframes rotating {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    height: 100vh;
    left: 0;
    top: 0;
  }

  .header-title {
    font-size: 16px;
  }

  .username,
  .system-time-chip {
    display: none;
  }
}
</style>


