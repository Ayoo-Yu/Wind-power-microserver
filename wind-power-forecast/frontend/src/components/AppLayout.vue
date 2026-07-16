<template>
  <el-container class="app-container">
    <div v-if="dbUnavailable" class="db-maintenance-banner">
      数据库维护中，部分数据暂不可用。系统将在数据库恢复后自动重连。
    </div>

    <div v-if="isAuthLoading" class="auth-loading-overlay">
      <div class="auth-loading-container">
        <el-icon class="loading-icon"><Loading /></el-icon>
        <div class="auth-loading-text">认证状态检查中...</div>
      </div>
    </div>

    <el-aside ref="sidebarRef" :width="isCollapsed ? '72px' : '248px'" class="sidebar">
      <div class="brand" @click="toggleCollapse">
        <img src="@/assets/Hust_logo.png" alt="华中科技大学" class="brand-logo" />
        <div v-if="!isCollapsed" class="brand-copy">
          <strong>风电功率预测系统</strong>
          <span>预测运行 · 数据治理 · 质量评估</span>
        </div>
      </div>

      <el-menu
        ref="menuRef"
        :default-active="activeMenu"
        :default-openeds="defaultOpeneds"
        :unique-opened="true"
        class="el-menu-vertical"
        :collapse="isCollapsed"
        @select="handleSelect"
      >
        <el-menu-item index="/">
          <el-icon><HomeFilled /></el-icon>
          <template #title>首页总览</template>
        </el-menu-item>

        <el-sub-menu index="/group-predict" v-if="hasPermission('auto_predictions') || hasPermission('manual_intervention_workspace')">
          <template #title>
            <el-icon><Timer /></el-icon>
            <span>预测运行</span>
          </template>
          <el-menu-item index="/autopredict" v-if="hasPermission('auto_predictions')">预测任务</el-menu-item>
          <el-menu-item index="/manual-workspace" v-if="hasPermission('manual_intervention_workspace') || hasPermission('auto_predictions')">
            人工修正
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="/group-analysis" v-if="hasPermission('view_all_data') || hasPermission('view_accuracy_report')">
          <template #title>
            <el-icon><DataAnalysis /></el-icon>
            <span>结果分析</span>
          </template>
          <el-menu-item index="/powercompare" v-if="hasPermission('view_all_data')">预测曲线与考核</el-menu-item>
          <el-menu-item index="/accuracy-report" v-if="hasPermission('view_accuracy_report') || hasPermission('view_all_data')">
            月度准确率报表
          </el-menu-item>
          <el-menu-item index="/power-curve" v-if="hasPermission('view_all_data')">风速功率曲线</el-menu-item>
        </el-sub-menu>

        <el-sub-menu
          index="/group-exchange"
          v-if="hasPermission('manage_weather_data') || hasPermission('manage_data_import') || hasPermission('manage_data_quality') || hasPermission('view_all_data') || (reportingEnabled && hasPermission('manage_reports'))"
        >
          <template #title>
            <el-icon><Upload /></el-icon>
            <span>数据管理</span>
          </template>
          <el-menu-item index="/weatherdatafetcher" v-if="hasPermission('manage_weather_data')">气象数据接入</el-menu-item>
          <el-menu-item index="/data-population" v-if="hasPermission('manage_data_import')">历史数据补齐</el-menu-item>
          <el-menu-item index="/data-quality" v-if="hasPermission('manage_data_quality') || hasPermission('view_all_data')">
            数据质量与限电
          </el-menu-item>
          <el-menu-item index="/reportmanagement" v-if="reportingEnabled && hasPermission('manage_reports')">上报配置</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="/group-ops" v-if="hasPermission('view_alarm_center') || hasPermission('manage_reports')">
          <template #title>
            <el-icon><WarnTriangleFilled /></el-icon>
            <span>运行保障</span>
          </template>
          <el-menu-item index="/operations-center" v-if="hasPermission('view_alarm_center')">
            链路运行状态
          </el-menu-item>
          <el-menu-item index="/alarm-center" v-if="hasPermission('view_alarm_center') || hasPermission('manage_reports')">告警处置</el-menu-item>
        </el-sub-menu>

        <el-sub-menu
          index="/group-admin"
          v-if="hasPermission('manage_reports') || hasPermission('manage_users') || hasPermission('manage_roles') || hasPermission('manage_system_settings') || hasPermission('system_maintenance') || hasPermission('view_audit_logs')"
        >
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>系统配置</span>
          </template>
          <el-menu-item index="/farmmanagement" v-if="hasPermission('manage_reports')">场站配置</el-menu-item>
          <el-menu-item index="/scada-connections" v-if="hasPermission('manage_system_settings')">SCADA数据源</el-menu-item>
          <el-menu-item index="/users" v-if="hasPermission('manage_users') || hasPermission('manage_roles')">账号与权限</el-menu-item>
          <el-menu-item index="/system-settings" v-if="hasPermission('manage_system_settings') || hasPermission('system_maintenance')">
            系统基础配置
          </el-menu-item>
          <el-menu-item index="/database-governance" v-if="hasPermission('system_maintenance')">
            数据库治理
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
        </div>

        <div class="header-right">
          <el-tooltip
            v-if="capabilityIssues.length"
            :content="capabilityIssueText"
            placement="bottom"
          >
            <div class="capability-chip">
              {{ capabilityIssues.length }} 项能力待接入
            </div>
          </el-tooltip>

          <el-badge v-if="canViewAlerts" :value="alertCount" :max="99" class="alert-badge">
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

      <nav class="workspace-tabs" aria-label="已打开页面">
        <div ref="tabsScrollerRef" class="workspace-tabs__scroller" role="tablist">
          <div
            v-for="tab in openTabs"
            :key="tab.key"
            class="workspace-tab"
            :class="{ 'is-active': tab.key === activeTabKey, 'is-fixed': !tab.closable }"
            :data-tab-key="tab.key"
          >
            <button
              type="button"
              class="workspace-tab__main"
              role="tab"
              :aria-selected="tab.key === activeTabKey"
              :title="tab.title"
              @click="activateTab(tab)"
              @keydown.delete.prevent="closeTab(tab.key)"
            >
              <el-icon class="workspace-tab__icon">
                <HomeFilled v-if="!tab.closable" />
                <Document v-else />
              </el-icon>
              <span>{{ tab.title }}</span>
            </button>
            <button
              v-if="tab.closable"
              type="button"
              class="workspace-tab__close"
              :aria-label="`关闭${tab.title}`"
              :title="`关闭${tab.title}`"
              @click.stop="closeTab(tab.key)"
            >
              <el-icon><Close /></el-icon>
            </button>
          </div>
        </div>
      </nav>

      <el-main ref="mainContentRef" class="main-content">
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
import { ref, computed, provide, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getCurrentUser } from '../api/auth'
import { isAuthReady, isAuthLoading } from '../store/authReady'
import { dbState } from '../api/axios'
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
  Bell,
  Document,
  Close
} from '@element-plus/icons-vue'
import FarmSelector from './FarmSelector.vue'
import farmService from '../utils/farmService'
import { getCapabilities } from '../api/capabilityApi'
import {
  closeWorkspaceTab,
  getWorkspaceTabKey,
  restoreWorkspaceTabs,
  routeToWorkspaceTab,
  upsertWorkspaceTab
} from '../utils/workspaceTabs.mjs'

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
    Document,
    Close,
    FarmSelector
  },
  setup() {
    const router = useRouter()
    const route = useRoute()

    const isCollapsed = ref(false)
    const menuRef = ref(null)
    const sidebarRef = ref(null)
    const mainContentRef = ref(null)
    const tabsScrollerRef = ref(null)
    const isAnimatedBackground = ref(true)
    const currentUser = ref(null)
    const uiText = UI_TEXT.appLayout
    const systemTime = ref('')
    const alertCount = ref(0)
    const dbUnavailable = ref(dbState.unavailable)
    const capabilities = ref([])
    let timeTicker = null
    let capabilityTicker = null
    let removeWorkspaceGuard = null
    let skipWorkspacePersistence = false
    const reportingEnabled = import.meta.env.VITE_REPORTING_ENABLED === 'true'
    const menuGroups = ['/group-predict', '/group-analysis', '/group-exchange', '/group-ops', '/group-admin']
    const workspaceStateKey = 'wind_power_workspace_tabs_v1'
    const workspaceScrollPositions = new Map()

    const unsubscribeDb = dbState.onChange((val) => { dbUnavailable.value = val })

    provide('isAnimatedBackground', isAnimatedBackground)

    const activeMenu = computed(() => (route.path === '/' ? '/' : route.path))
    const activeTabKey = computed(() => getWorkspaceTabKey(route))
    const activeGroup = computed(() => {
      if (['/autopredict', '/manual-workspace'].includes(route.path)) return '/group-predict'
      if (['/powercompare', '/accuracy-report', '/power-curve'].includes(route.path)) return '/group-analysis'
      if (['/weatherdatafetcher', '/data-population', '/data-quality', '/reportmanagement'].includes(route.path)) return '/group-exchange'
      if (['/operations-center', '/alarm-center'].includes(route.path)) return '/group-ops'
      if (['/farmmanagement', '/scada-connections', '/users', '/users/roles', '/system-settings', '/database-governance', '/users/audit-logs'].includes(route.path)) return '/group-admin'
      return ''
    })
    const defaultOpeneds = computed(() => (activeGroup.value ? [activeGroup.value] : []))
    const openTabs = ref([])
    const keepAliveRouteNames = computed(() =>
      openTabs.value
        .filter(tab => tab.name)
        .map(tab => tab.name)
    )
    const canViewAlerts = computed(() => hasPermission('view_alarm_center') || hasPermission('manage_reports'))
    const capabilityIssues = computed(() =>
      capabilities.value.filter(
        item => item.attention_required !== false && item.availability !== 'available'
      )
    )
    const capabilityIssueText = computed(() =>
      capabilityIssues.value.map(item => `${item.name}: ${item.reason}`).join('；')
    )

    const fetchCapabilities = async () => {
      try {
        const response = await getCapabilities()
        capabilities.value = response?.data?.capabilities || []
      } catch (error) {
        capabilities.value = []
        console.warn('系统能力清单加载失败:', error?.message || error)
      }
    }

    const refreshCapabilitiesWhenVisible = () => {
      if (document.visibilityState === 'visible') {
        fetchCapabilities()
      }
    }

    provide('capabilities', capabilities)

    const persistWorkspaceState = () => {
      try {
        sessionStorage.setItem(workspaceStateKey, JSON.stringify({
          tabs: openTabs.value,
          scrollPositions: Object.fromEntries(workspaceScrollPositions)
        }))
      } catch {
        // 浏览器禁用会话存储时，当前会话内的页签仍可正常工作。
      }
    }

    const loadWorkspaceState = () => {
      let storedState = {}
      try {
        storedState = JSON.parse(sessionStorage.getItem(workspaceStateKey) || '{}')
      } catch {
        storedState = {}
      }

      Object.entries(storedState.scrollPositions || {}).forEach(([key, value]) => {
        workspaceScrollPositions.set(key, Math.max(0, Number(value) || 0))
      })

      const homeTab = routeToWorkspaceTab(router.resolve('/'))
      const restoredTabs = restoreWorkspaceTabs(storedState.tabs, target => router.resolve(target))
        .filter(tab => tab.key !== homeTab?.key)
      openTabs.value = homeTab ? [homeTab, ...restoredTabs] : restoredTabs
      openTabs.value = upsertWorkspaceTab(openTabs.value, route)
      persistWorkspaceState()
    }

    const rememberScrollPosition = (routeLike) => {
      const key = getWorkspaceTabKey(routeLike)
      const mainElement = mainContentRef.value?.$el || mainContentRef.value
      if (!key || !mainElement) return
      workspaceScrollPositions.set(key, Math.max(0, mainElement.scrollTop || 0))
      persistWorkspaceState()
    }

    const restoreScrollPosition = async (routeLike) => {
      const key = getWorkspaceTabKey(routeLike)
      await nextTick()
      window.requestAnimationFrame(() => {
        const mainElement = mainContentRef.value?.$el || mainContentRef.value
        if (mainElement) mainElement.scrollTop = workspaceScrollPositions.get(key) || 0
      })
    }

    const scrollActiveTabIntoView = async () => {
      await nextTick()
      tabsScrollerRef.value
        ?.querySelector('.workspace-tab.is-active')
        ?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' })
    }

    const syncWorkspaceForRoute = async () => {
      if (!route.name || route.name === 'Login') return
      openTabs.value = upsertWorkspaceTab(openTabs.value, route)
      persistWorkspaceState()
      await restoreScrollPosition(route)
      await scrollActiveTabIntoView()
    }

    const activateTab = (tab) => {
      if (!tab || tab.key === activeTabKey.value) return
      router.push(tab.fullPath || tab.path)
    }

    const closeTab = (key) => {
      const result = closeWorkspaceTab(openTabs.value, key, activeTabKey.value)
      if (result.tabs.length === openTabs.value.length) return

      openTabs.value = result.tabs
      persistWorkspaceState()

      if (result.nextTab) {
        router.replace(result.nextTab.fullPath || result.nextTab.path).finally(() => {
          workspaceScrollPositions.delete(key)
          persistWorkspaceState()
        })
      } else {
        workspaceScrollPositions.delete(key)
        persistWorkspaceState()
      }
    }

    loadWorkspaceState()

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
        skipWorkspacePersistence = true
        sessionStorage.removeItem(workspaceStateKey)
        if (router.currentRoute.value.path !== '/login') {
          router.push('/login')
        }
        return
      }

      try {
        const latestUser = await getCurrentUser()
        localStorage.setItem('user', JSON.stringify(latestUser))
        currentUser.value = latestUser
        isAuthReady.value = true
        await syncMenuForRoute()
      } catch {
        localStorage.removeItem('accessToken')
        localStorage.removeItem('user')
        skipWorkspacePersistence = true
        sessionStorage.removeItem(workspaceStateKey)
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

    const syncCollapseForViewport = () => {
      if (window.innerWidth <= 980) {
        isCollapsed.value = true
      }
    }

    const handleSelect = (index) => {
      if (route.path !== index) router.push(index)
    }

    const syncMenuForRoute = async () => {
      await nextTick()
      const sidebarElement = sidebarRef.value?.$el || sidebarRef.value
      if (sidebarElement) sidebarElement.scrollTop = 0

      if (!currentUser.value || !menuRef.value) return
      menuGroups.forEach(group => {
        if (group !== activeGroup.value) menuRef.value.close(group)
      })
      if (activeGroup.value) menuRef.value.open(activeGroup.value)
    }

    watch(() => route.path, syncMenuForRoute)
    watch(() => route.fullPath, syncWorkspaceForRoute)

    const handleCommand = (command) => {
      if (command === 'logout') {
        handleLogout()
      }
    }

    const handleFarmChanged = (farmCode) => {
      farmService.setCurrentFarm(farmCode)
    }

    const goAlerts = () => {
      if (!canViewAlerts.value) {
        ElMessage.warning('当前账号没有访问告警中心的权限')
        return
      }
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
          skipWorkspacePersistence = true
          sessionStorage.removeItem(workspaceStateKey)
          ElMessage.success('已成功退出登录')
          router.push('/login')
        })
        .catch(() => {})
    }

    onMounted(() => {
      removeWorkspaceGuard = router.beforeEach((to, from) => {
        if (!skipWorkspacePersistence && from.name && from.name !== 'Login') rememberScrollPosition(from)
        return true
      })
      syncCollapseForViewport()
      refreshSystemTime()
      timeTicker = setInterval(refreshSystemTime, 1000)
      fetchCurrentUser()
      fetchCapabilities()
      capabilityTicker = setInterval(fetchCapabilities, 30000)
      window.addEventListener('resize', syncCollapseForViewport)
      document.addEventListener('visibilitychange', refreshCapabilitiesWhenVisible)
      syncMenuForRoute()
      restoreScrollPosition(route)
    })

    onUnmounted(() => {
      if (timeTicker) {
        clearInterval(timeTicker)
      }
      if (capabilityTicker) {
        clearInterval(capabilityTicker)
      }
      window.removeEventListener('resize', syncCollapseForViewport)
      document.removeEventListener('visibilitychange', refreshCapabilitiesWhenVisible)
      if (removeWorkspaceGuard) removeWorkspaceGuard()
      unsubscribeDb()
    })

    return {
      isCollapsed,
      menuRef,
      sidebarRef,
      mainContentRef,
      tabsScrollerRef,
      activeMenu,
      activeTabKey,
      openTabs,
      defaultOpeneds,
      keepAliveRouteNames,
      dbUnavailable,
      toggleCollapse,
      handleSelect,
      activateTab,
      closeTab,
      userInitial,
      userName,
      alertCount,
      uiText,
      systemTime,
      goAlerts,
      canViewAlerts,
      handleCommand,
      handleFarmChanged,
      hasPermission,
      isAuthReady,
      isAuthLoading,
      capabilityIssues,
      capabilityIssueText,
      reportingEnabled
    }
  }
}
</script>

<style scoped>
.app-container {
  height: 100vh;
  position: relative;
  background: var(--bg-root);
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
  background: var(--bg-root) !important;
}

.main-container {
  min-width: 0;
}

.main-content {
  padding: 0;
  overflow-y: auto;
}

.workspace-tabs {
  flex: 0 0 46px;
  min-width: 0;
  height: 46px;
  display: flex;
  align-items: center;
  padding: 6px 18px;
  background: rgba(255, 255, 255, 0.96);
  border-bottom: 1px solid var(--border-color);
  z-index: 998;
}

.workspace-tabs__scroller {
  min-width: 0;
  width: 100%;
  display: flex;
  align-items: center;
  gap: 6px;
  overflow-x: auto;
  overscroll-behavior-x: contain;
  scrollbar-width: thin;
  scrollbar-color: #c8d2ca transparent;
}

.workspace-tabs__scroller::-webkit-scrollbar {
  height: 4px;
}

.workspace-tabs__scroller::-webkit-scrollbar-thumb {
  background: #c8d2ca;
  border-radius: 999px;
}

.workspace-tab {
  flex: 0 0 auto;
  min-width: 112px;
  max-width: 210px;
  height: 32px;
  display: flex;
  align-items: center;
  color: var(--text-secondary);
  background: #f4f6f4;
  border: 1px solid transparent;
  border-radius: 8px;
  transition: color var(--transition-fast), background-color var(--transition-fast), border-color var(--transition-fast);
}

.workspace-tab:hover {
  color: var(--text-primary);
  background: #eef2ef;
}

.workspace-tab.is-active {
  color: var(--accent);
  background: #ffffff;
  border-color: #bfd5c8;
}

.workspace-tab__main {
  min-width: 0;
  flex: 1;
  height: 100%;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 0 9px;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}

.workspace-tab__main span {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.workspace-tab__icon {
  flex: 0 0 auto;
  font-size: 14px;
}

.workspace-tab__close {
  flex: 0 0 24px;
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  margin-right: 4px;
  padding: 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
}

.workspace-tab__close:hover,
.workspace-tab__close:focus-visible {
  color: var(--danger);
  background: var(--danger-soft);
  outline: none;
}

.workspace-tab__main:focus-visible {
  border-radius: 7px;
  outline: 2px solid rgba(47, 138, 95, 0.28);
  outline-offset: -2px;
}

.sidebar {
  background: #fbfcfb;
  border-right: 1px solid var(--border-color);
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 1000;
  box-shadow: none;
}

.brand {
  height: 72px;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 11px;
  padding: 13px 16px;
  cursor: pointer;
  border-bottom: 1px solid var(--border-color);
}

.brand-logo {
  width: 40px;
  height: 40px;
  flex: 0 0 40px;
  object-fit: contain;
  filter: none;
}

.brand-copy {
  min-width: 0;
  display: grid;
  gap: 3px;
}

.brand-copy strong {
  overflow: hidden;
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 650;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.brand-copy span {
  overflow: hidden;
  color: var(--text-muted);
  font-size: 11px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.el-menu-vertical,
.el-menu {
  border-right: none;
  background: transparent;
  border: none;
}

.el-menu-item {
  color: var(--text-secondary);
  height: 46px;
  margin: 4px 10px;
  border-radius: 9px;
}

:deep(.el-sub-menu__title) {
  color: var(--text-secondary);
  height: 46px;
  margin: 4px 10px;
  border-radius: 9px;
}

:deep(.el-sub-menu .el-menu-item) {
  min-width: 0;
  height: 40px;
  margin: 2px 10px;
  padding-left: 54px !important;
}

.el-menu-item.is-active {
  color: var(--accent);
  background: var(--accent-soft);
  box-shadow: inset 3px 0 0 var(--accent);
}

.el-menu-item:hover {
  color: var(--text-primary);
  background: #f0f3f0;
}

:deep(.el-sub-menu__title:hover) {
  color: var(--text-primary);
  background: #f0f3f0;
}

.el-menu-item .el-icon {
  font-size: 20px;
}

.header {
  height: 72px;
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--border-color);
  z-index: 999;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.collapse-btn {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  font-size: 18px;
  cursor: pointer;
  color: var(--text-secondary);
  border-radius: 8px;
  transition: background-color var(--transition-fast), color var(--transition-fast);
}

.collapse-btn:hover {
  color: var(--text-primary);
  background: var(--bg-muted);
}

.alert-badge :deep(.el-badge__content) {
  background: var(--danger);
  border-color: transparent;
}

.alert-btn {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 1px solid var(--border-color);
  background: #ffffff;
  color: var(--text-secondary);
  transition: all var(--transition-normal);
}
.alert-btn:hover {
  color: var(--text-primary);
  border-color: var(--border-strong);
  background: var(--bg-card-soft);
}

.system-time-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 2px;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
}

.capability-chip {
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid #e7d3ad;
  background: var(--warning-soft);
  color: #966019;
  font-size: 12px;
  cursor: help;
}

.time-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent-2);
  box-shadow: none;
}

.time-value {
  color: var(--text-primary);
  font-family: var(--font-mono);
}

.user-profile {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 5px 8px;
  border-radius: 20px;
  transition: background-color var(--transition-fast);
  background: transparent;
}

.user-profile:hover {
  background: var(--bg-muted);
}

.username {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.db-maintenance-banner {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 9999;
  background: #f3d598;
  color: #5b3a0c;
  text-align: center;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.auth-loading-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(245, 247, 244, 0.88);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
}

.auth-loading-container {
  background: #ffffff;
  border: 1px solid var(--border-color);
  padding: 30px;
  border-radius: 12px;
  box-shadow: var(--shadow-float);
  display: flex;
  flex-direction: column;
  align-items: center;
}

.auth-loading-text {
  margin-top: 15px;
  font-size: 16px;
  color: var(--text-secondary);
}

.loading-icon {
  font-size: 32px;
  color: var(--accent);
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

  .main-container {
    width: calc(100% - 72px);
    min-width: 0;
    margin-left: 72px;
  }

  .username,
  .system-time-chip {
    display: none;
  }

  .workspace-tabs {
    padding-inline: 10px;
  }

  .workspace-tab {
    min-width: 104px;
    max-width: 168px;
  }
}

@media (max-width: 1100px) {
  .header {
    padding: 0 14px;
  }

  .header-left,
  .header-right {
    gap: 10px;
  }

  .username,
  .system-time-chip,
  .capability-chip {
    display: none;
  }

  .user-profile {
    padding: 5px;
  }
}
</style>


