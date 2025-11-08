<!-- src/components/Layout.vue -->
<template>
  <el-container class="app-container">
    <!-- 全局认证加载指示器 -->
    <div v-if="isAuthLoading" class="auth-loading-overlay">
      <div class="auth-loading-container">
        <el-icon class="loading-icon"><Loading /></el-icon>
        <div class="auth-loading-text">认证状态检查中...</div>
      </div>
    </div>

    <!-- 背景容器：内联样式根据开关动态控制动画播放状态 -->
    <div class="background-container">
      <div class="background-aurora" :style="backgroundStyle"></div>
      <div class="background-grid"></div>
      <div class="background-glow"></div>
    </div>

    <!-- 侧边栏 -->
    <el-aside
      :width="isCollapsed ? '64px' : '240px'"
      class="sidebar"
    >
      <!-- 品牌标识 -->
      <div class="brand" @click="toggleCollapse">
        <img
          v-if="!isCollapsed"
          src="@/assets/Sanxia_logo.png"
          alt="Logo"
          class="brand-logo"
        />
        <el-icon v-else class="collapse-icon">
          <Expand />
        </el-icon>
      </div>

      <!-- 菜单 -->
      <el-menu
        :default-active="activeMenu"
        class="el-menu-vertical"
        :collapse="isCollapsed"
        @select="handleSelect"
      >
        <el-menu-item index="/">
          <el-icon><HomeFilled /></el-icon>
          <template #title>首页</template>
        </el-menu-item>

        <el-menu-item index="/windfarm-management" v-if="hasPermission('view_all_data')">
          <el-icon><OfficeBuilding /></el-icon>
          <template #title>风电场管理</template>
        </el-menu-item>

        <el-menu-item index="/modeltrain" v-if="hasPermission('train_models')">
          <el-icon><DataAnalysis /></el-icon>
          <template #title>模型训练</template>
        </el-menu-item>

        <el-menu-item index="/powerpredict" v-if="hasPermission('run_predictions')">
          <el-icon><TrendCharts /></el-icon>
          <template #title>功率预测</template>
        </el-menu-item>

        <el-menu-item index="/autopredict" v-if="hasPermission('auto_predictions')">
          <el-icon><Timer /></el-icon>
          <template #title>自动预测</template>
        </el-menu-item>

        <el-menu-item index="/powercompare" v-if="hasPermission('view_all_data')">
          <el-icon><Histogram /></el-icon>
          <template #title>功率对比</template>
        </el-menu-item>

        <el-menu-item index="/physicalsimulation" v-if="hasPermission('run_simulations')">
          <el-icon><WindPower /></el-icon>
          <template #title>物理仿真</template>
        </el-menu-item>

        <el-menu-item index="/systemmaintenance" v-if="hasPermission('system_maintenance')">
          <el-icon><Tools /></el-icon>
          <template #title>系统维护</template>
        </el-menu-item>

        <el-menu-item index="/reportmanagement" v-if="hasPermission('manage_reports')">
          <el-icon><Upload /></el-icon>
          <template #title>上报管理</template>
        </el-menu-item>

        <el-menu-item index="/weatherdatafetcher" v-if="hasPermission('manage_weather_data')">
          <el-icon><Cloudy /></el-icon>
          <template #title>气象数据拉取</template>
        </el-menu-item>

        <el-menu-item index="/users" v-if="hasPermission('manage_users')">
          <el-icon><User /></el-icon>
          <template #title>用户管理</template>
        </el-menu-item>

      </el-menu>
    </el-aside>

    <!-- 主要内容区域 -->
    <el-container class="main-container">
      <!-- 顶部导航栏 -->
      <el-header class="header">
        <div class="header-left">
          <el-icon class="collapse-btn" @click="toggleCollapse">
            <Fold v-if="!isCollapsed" />
            <Expand v-else />
          </el-icon>
          <div class="header-text">
            <h1 class="header-title">中国三峡集团风电功率预测平台</h1>
            <span class="header-subtitle">Wind Power Intelligence Console</span>
          </div>
          <span class="status-indicator header-status">系统在线</span>
        </div>
        <div class="header-right">
          <div class="wind-farm-wrapper">
            <span class="wind-farm-label">当前风电场</span>
            <el-select
              v-model="selectedWindFarm"
              size="small"
              class="wind-farm-select"
              :loading="isWindFarmLoading"
              placeholder="选择场站"
              filterable
            >
              <el-option
                v-for="farm in windFarms"
                :key="farm.farm_code || farm.farm_name"
                :label="farm.farm_name || farm.farm_code || '默认风电场'"
                :value="farm.farm_code || farm.farm_name || 'default-farm'"
              />
              <el-option
                v-if="!windFarms.length"
                :value="selectedWindFarm"
                :label="selectedWindFarmName"
              />
            </el-select>
          </div>
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

      <!-- 内容区域 -->
      <el-main class="main-content">
        <router-view></router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script>
import { ref, computed, provide, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import axiosInstance from '../api/axios'
import { isAuthReady, isAuthLoading } from '../store/authReady' // 导入认证状态
import { useWindFarmStore } from '../store/windFarm'

// 引入 Element Plus 图标
import {
  HomeFilled,
  DataAnalysis,
  Fold,
  Expand,
  TrendCharts,
  Timer,
  User,
  Loading,
  WindPower,
  Tools,
  Upload,
  Histogram,
  Cloudy,
  OfficeBuilding
} from '@element-plus/icons-vue'

export default {
  name: 'AppLayout',
  components: {
    HomeFilled,
    DataAnalysis,
    Fold,
    Expand,
    TrendCharts,
    Timer,
    User,
    Loading,
    WindPower,
    Tools,
    Upload,
    Histogram,
    Cloudy,
    OfficeBuilding,
  },
  setup() {
    const isCollapsed = ref(false)
    const isAnimatedBackground = ref(true)
    const router = useRouter()
    const route = useRoute()
    
    // 用户信息
    const currentUser = ref(null)

    const {
      windFarms,
      isLoading: isWindFarmLoading,
      selectedWindFarm,
      loadWindFarms,
      findWindFarmByCode,
    } = useWindFarmStore()

    const selectedWindFarmName = computed(() => {
      const code = selectedWindFarm.value
      const farm = findWindFarmByCode(code)
      if (farm) {
        if (farm.farm_name && farm.farm_code) {
          return `${farm.farm_name}`
        }
        return farm.farm_name || farm.farm_code
      }
      return code || '默认场站'
    })

    // 将 isAnimatedBackground 提供给子组件使用
    provide('isAnimatedBackground', isAnimatedBackground)
    provide('selectedWindFarm', selectedWindFarm)

    // 计算背景内联样式
    const backgroundStyle = computed(() => ({
      position: 'absolute',
      top: '0',
      left: '0',
      width: '100%',
      height: '100%',
      background: 'linear-gradient(120deg, rgba(19, 66, 130, 0.55) 0%, rgba(7, 20, 45, 0.92) 40%, rgba(30, 115, 224, 0.45) 100%)',
      backgroundSize: '220% 220%',
      opacity: isAnimatedBackground.value ? '0.95' : '0.75',
      filter: 'blur(0px)',
      transition: 'opacity 0.6s ease',
      animation: 'auroraFlow 20s ease infinite',
      animationPlayState: isAnimatedBackground.value ? 'running' : 'paused'
    }))

    const activeMenu = computed(() => (route.path === '/' ? '/' : route.path))
    
    // 计算用户名首字母
    const userInitial = computed(() => {
      const userStr = localStorage.getItem('user')
      if (!userStr) return 'U'
      const user = JSON.parse(userStr)
      return user.full_name ? user.full_name.charAt(0).toUpperCase() : 
             user.username.charAt(0).toUpperCase()
    })
    
    // 计算用户显示名称
    const userName = computed(() => {
      const userStr = localStorage.getItem('user')
      if (!userStr) return '用户'
      const user = JSON.parse(userStr)
      return user.full_name || user.username
    })
    
    // 获取当前用户信息
    const fetchCurrentUser = async () => {
      isAuthLoading.value = true; // 开始认证检查
      isAuthReady.value = false; // 重置认证就绪状态
      let isAuthenticated = false; // 引入局部变量跟踪验证结果
      console.log('开始检查认证状态...');
      
      try {
        // 检查本地存储中是否有访问令牌
        const token = localStorage.getItem('accessToken');
        const userStr = localStorage.getItem('user');
        
        // 记录当前认证状态
        console.log('本地存储检查:', { 
          tokenExists: !!token, 
          userExists: !!userStr 
        });
        
        // 如果没有令牌或用户信息，不尝试验证
        if (!token || !userStr) {
          console.warn('无本地认证信息，不尝试验证');
          // 清除可能部分存在的认证信息
          localStorage.removeItem('accessToken');
          localStorage.removeItem('user');
          // 不在这里跳转，让finally块处理
        } else {
          // 尝试解析本地用户数据
          try {
            // 尝试加载本地存储的用户信息
            currentUser.value = JSON.parse(userStr);
            console.log('本地用户信息已解析:', currentUser.value?.username);
          } catch (parseError) {
            console.error('解析本地用户信息失败:', parseError);
            localStorage.removeItem('accessToken');
            localStorage.removeItem('user');
            currentUser.value = null; // 确保清空
            // 继续进入finally块
          }
          
          // 如果Token和用户信息都存在，尝试验证Token有效性
          if (token && currentUser.value) {
            console.log('本地有Token和用户，尝试调用/auth/me验证...');
            try {
              await axiosInstance.get('auth/me');
              console.log('Token验证成功 (通过/auth/me)');
              isAuthenticated = true; // 验证成功！
            } catch (apiError) {
              console.error('/auth/me验证失败:', apiError.message);
              // 401错误会被响应拦截器处理（清除Token, 跳转）
              if (apiError.response && apiError.response.status !== 401) {
                console.log('/auth/me返回非401错误，视为未认证');
              }
              // isAuthenticated保持false
            }
          } else {
            console.log('Token或本地用户信息不完整，跳过API验证');
          }
        }
      } catch (error) {
        console.error('fetchCurrentUser出现意外错误:', error);
        // 出现意外错误，视为未认证
        isAuthenticated = false;
      } finally {
        // 认证检查流程完成，直接根据验证结果设置状态
        isAuthReady.value = isAuthenticated;
        isAuthLoading.value = false;
        console.log('最终认证状态:', { 
          isAuthReady: isAuthReady.value, 
          isAuthLoading: isAuthLoading.value,
          isAuthenticated: isAuthenticated
        });
        
        // 如果检查完成但未认证，并且当前不在登录页，执行跳转
        if (!isAuthReady.value && !isAuthLoading.value && router.currentRoute.value.path !== '/login') {
          console.log('认证检查完成但未通过，且不在登录页，执行跳转...');
          // 确保Token和用户信息已被清除
          localStorage.removeItem('accessToken');
          localStorage.removeItem('user');
          currentUser.value = null;
          router.push('/login');
        }
      }
    }
    
    // 检查权限
    const hasPermission = (permission) => {
      // 简化权限检查，只要是管理员就有所有权限
      if (!currentUser.value) {
        console.log('当前用户未加载，无法检查权限');
        return false;
      }
      
      // 系统管理员角色直接授予所有权限
      if (currentUser.value.role === '系统管理员') {
        console.log(`用户是系统管理员，自动授予权限: ${permission}`);
        return true;
      }
      
      // 检查用户的权限列表
      if (currentUser.value.permissions) {
        console.log(`检查权限 ${permission}，当前权限信息:`, currentUser.value.permissions);
        
        // 处理权限可能是数组或嵌套对象的情况
        let permissions = currentUser.value.permissions;
        
        // 如果权限是对象且有permissions属性
        if (typeof permissions === 'object' && !Array.isArray(permissions) && permissions.permissions) {
          console.log('权限是嵌套对象格式，提取permissions数组');
          permissions = permissions.permissions;
        }
        
        // 如果权限是数组
        if (Array.isArray(permissions)) {
          const hasPermission = permissions.includes(permission);
          console.log(`权限检查结果 ${permission}: ${hasPermission ? '有权限' : '无权限'}`);
          return hasPermission;
        } else {
          console.log(`权限格式不是数组: ${typeof permissions}`);
        }
      } else {
        console.log('用户没有权限信息');
      }
      
      console.log(`权限检查失败: ${permission}`);
      return false;
    }

    // 将 hasPermission 提供给子组件使用
    provide('hasPermission', hasPermission)

    const toggleCollapse = () => {
      isCollapsed.value = !isCollapsed.value
    }

    const handleSelect = (index) => {
      router.push(index)
    }
    
    // 处理下拉菜单命令
    const handleCommand = (command) => {
      if (command === 'logout') {
        handleLogout()
      }
    }
    
    // 处理退出登录
    const handleLogout = () => {
      ElMessageBox.confirm('确定要退出登录吗?', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }).then(() => {
        // 清除localStorage中的所有用户相关信息
        localStorage.removeItem('user')
        
        // 清除访问令牌 (关键修改)
        localStorage.removeItem('accessToken')
        
        ElMessage.success('已成功退出登录')
        
        // 重定向到登录页
        router.push('/login')
      }).catch(() => {
        // 用户取消操作
      })
    }
    
    // 生命周期钩子
    onMounted(() => {
      fetchCurrentUser()
      loadWindFarms()
    })

    return {
      isCollapsed,
      isAnimatedBackground,
      activeMenu,
      toggleCollapse,
      handleSelect,
      backgroundStyle,
      currentUser,
      userInitial,
      userName,
      handleCommand,
      hasPermission,
      isAuthReady, // 暴露认证状态
      isAuthLoading, // 暴露认证加载状态
      windFarms,
      isWindFarmLoading,
      selectedWindFarm,
      selectedWindFarmName,
    }
  },
}
</script>

<style scoped>
.app-container {
  position: relative;
  height: 100vh;
  overflow: hidden;
  color: var(--text-primary);
}

.dialog-footer {
  text-align: right;
  margin-top: 20px;
}

.custom-form :deep(.el-form-item__content) {
  flex-wrap: nowrap;
  justify-content: flex-start;
}

.background-container {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  overflow: hidden;
}

.background-aurora,
.background-grid,
.background-glow {
  position: absolute;
  inset: 0;
}

.background-aurora {
  mix-blend-mode: screen;
  opacity: 0.9;
}

.background-grid {
  background-image:
    linear-gradient(90deg, rgba(56, 196, 255, 0.08) 1px, transparent 0),
    linear-gradient(0deg, rgba(56, 196, 255, 0.08) 1px, transparent 0);
  background-size: 160px 160px;
  opacity: 0.25;
  animation: gridDrift 45s linear infinite;
}

.background-glow {
  background: radial-gradient(circle at 28% 18%, rgba(34, 246, 170, 0.22), transparent 62%),
              radial-gradient(circle at 70% 82%, rgba(56, 196, 255, 0.18), transparent 58%);
  filter: blur(18px);
  opacity: 0.7;
  animation: glowPulse 14s ease-in-out infinite;
}

@keyframes auroraFlow {
  0% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0% 50%;
  }
}

@keyframes gridDrift {
  0% {
    background-position: 0 0, 0 0;
  }
  100% {
    background-position: 160px 160px, 160px 160px;
  }
}

@keyframes glowPulse {
  0%, 100% {
    opacity: 0.55;
  }
  50% {
    opacity: 0.86;
  }
}

.main-container,
.sidebar {
  position: relative;
  z-index: 1;
}

.main-container {
  background: transparent !important;
}

.main-content {
  background: transparent !important;
  padding: 32px 40px;
  overflow-y: auto;
}

.sidebar {
  display: flex;
  flex-direction: column;
  background: rgba(6, 18, 36, 0.9);
  border-right: 1px solid rgba(56, 196, 255, 0.24);
  backdrop-filter: blur(22px);
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 8px 0 32px rgba(3, 13, 30, 0.45);
}

.sidebar::after {
  content: '';
  position: absolute;
  top: 0;
  right: -1px;
  width: 1px;
  height: 100%;
  background: linear-gradient(180deg, transparent, rgba(56, 196, 255, 0.45), transparent);
  opacity: 0.6;
}

.brand {
  position: relative;
  height: 92px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  overflow: hidden;
  border-bottom: 1px solid rgba(56, 196, 255, 0.18);
}

.brand::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(56, 196, 255, 0.25), transparent 65%);
  opacity: 0.55;
}

.brand-logo {
  height: 42px;
  position: relative;
  filter: drop-shadow(0 6px 12px rgba(0, 168, 255, 0.35));
  transition: transform 0.3s ease;
}

.brand:hover .brand-logo {
  transform: scale(1.04);
}

.collapse-icon {
  font-size: 24px;
  color: var(--text-primary);
}

.el-menu-vertical {
  flex: 1;
  border-right: none;
  background: transparent;
  padding: 12px 0 24px;
}

.el-menu-vertical :deep(.el-menu) {
  border-right: none;
  background: transparent;
}

.el-menu-item {
  position: relative;
  color: var(--text-secondary);
  height: 52px;
  margin: 6px 12px;
  border-radius: 14px;
  letter-spacing: 0.08em;
  padding-left: 20px !important;
  transition: all 0.28s ease;
}

.el-menu-item::before {
  content: '';
  position: absolute;
  left: 12px;
  top: 50%;
  width: 4px;
  height: 0;
  border-radius: 999px;
  background: var(--accent-gradient);
  transform: translateY(-50%);
  transition: height 0.28s ease, opacity 0.28s ease;
  opacity: 0;
}

.el-menu-item .el-icon {
  font-size: 20px;
  margin-right: 12px;
}

.el-menu-item.is-active {
  color: var(--text-primary);
  background: rgba(56, 196, 255, 0.16);
  box-shadow: 0 12px 28px rgba(8, 48, 92, 0.45);
}

.el-menu-item.is-active::before {
  height: 70%;
  opacity: 1;
}

.el-menu-item:hover {
  color: var(--text-primary);
  background: rgba(56, 196, 255, 0.12);
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 0 36px;
  height: 84px;
  background: linear-gradient(120deg, rgba(6, 18, 36, 0.85) 0%, rgba(8, 24, 51, 0.92) 70%, rgba(8, 38, 73, 0.88) 100%);
  border-bottom: 1px solid rgba(56, 196, 255, 0.22);
  box-shadow: 0 12px 40px rgba(0, 12, 30, 0.5);
  backdrop-filter: blur(22px);
  position: sticky;
  top: 0;
  z-index: 5;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.collapse-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: 12px;
  background: rgba(5, 15, 34, 0.82);
  border: 1px solid rgba(56, 196, 255, 0.24);
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.25s ease;
}

.collapse-btn:hover {
  border-color: rgba(56, 196, 255, 0.4);
  box-shadow: 0 0 0 6px rgba(56, 196, 255, 0.12);
}

.header-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.header-title {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--text-primary);
}

.header-subtitle {
  font-size: 12px;
  letter-spacing: 0.38em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.header-status {
  font-size: 11px;
  letter-spacing: 0.24em;
  padding: 6px 16px;
  background: rgba(34, 246, 170, 0.16);
  border: 1px solid rgba(34, 246, 170, 0.45);
  border-radius: 999px;
  box-shadow: inset 0 0 12px rgba(34, 246, 170, 0.35);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: nowrap;
  flex-shrink: 0;
  padding-right: 16px;
}

.wind-farm-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
}

.wind-farm-label {
  font-size: 14px;
  letter-spacing: 0.12em;
  color: var(--text-secondary);
  white-space: nowrap;
}

.wind-farm-select {
  flex: 0 0 auto;
  min-width: 180px;
  max-width: 160px;
}

.wind-farm-select :deep(.el-input__wrapper) {
  min-height: 46px;
  background: rgba(5, 15, 34, 0.82) !important;
  border-radius: 14px !important;
  font-size: 16px;
  padding: 0 14px !important;
}

.wind-farm-select :deep(.el-select__caret) {
  color: var(--text-secondary);
}

.user-profile {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  border-radius: 999px;
  background: rgba(5, 16, 34, 0.8);
  border: 1px solid rgba(56, 196, 255, 0.24);
  box-shadow: 0 10px 30px rgba(4, 20, 40, 0.45);
  transition: all 0.25s ease;
  white-space: nowrap;
  flex-shrink: 0;
}

.user-profile::before {
  content: '';
  position: absolute;
  inset: -1px;
  border-radius: inherit;
  border: 1px solid rgba(56, 196, 255, 0.24);
  opacity: 0;
  transition: opacity 0.3s ease;
}

.user-profile:hover {
  border-color: rgba(56, 196, 255, 0.42);
  box-shadow: 0 18px 32px rgba(4, 20, 40, 0.6);
}

.user-profile:hover::before {
  opacity: 1;
}

.avatar {
  background: linear-gradient(135deg, #38C4FF, #1EFFA3);
  color: #041022;
  font-weight: 700;
}

.username {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: none;
  white-space: nowrap;
  color: var(--text-primary);
}

@media (max-width: 1024px) {
  .main-content {
    padding: 24px 24px 32px;
  }

  .header {
    padding: 0 24px;
    height: 74px;
  }

  .header-title {
    font-size: 18px;
  }

  .header-subtitle {
    display: none;
  }

  .header-status {
    display: none;
  }
}

@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    height: 100vh;
    left: 0;
    top: 0;
  }

  .username {
    display: none;
  }

  .wind-farm-select {
    display: none;
  }
}

.auth-loading-overlay {
  position: fixed;
  inset: 0;
  background: rgba(3, 9, 22, 0.78);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
  backdrop-filter: blur(12px);
}

.auth-loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 32px 44px;
  border-radius: 18px;
  background: rgba(6, 16, 34, 0.92);
  border: 1px solid rgba(56, 196, 255, 0.24);
  box-shadow: 0 30px 80px rgba(0, 10, 24, 0.7);
}

.auth-loading-text {
  font-size: 15px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.loading-icon {
  font-size: 34px;
  color: var(--accent-primary);
  animation: rotating 1.8s linear infinite;
}

@keyframes rotating {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>