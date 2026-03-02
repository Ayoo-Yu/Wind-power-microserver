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
      <div :style="backgroundStyle"></div>
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
          <h1 class="header-title">中国三峡集团风电功率预测平台</h1>
        </div>
        <div class="header-right">
          <!-- 场站选择器 -->
          <FarmSelector @farm-changed="handleFarmChanged" />

          <!-- 用户菜单 -->
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

// 引入 Element Plus 图标
import {
  HomeFilled,
  Fold,
  Expand,
  Timer,
  User,
  Loading,
  WindPower,
  Tools,
  Upload,
  Histogram,
  Cloudy
} from '@element-plus/icons-vue'

// 导入场站选择器组件
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
    WindPower,
    Tools,
    Upload,
    Histogram,
    Cloudy,
    FarmSelector,
  },
  setup() {
    const isCollapsed = ref(false)
    const isAnimatedBackground = ref(true)
    const router = useRouter()
    const route = useRoute()
    
    // 用户信息
    const currentUser = ref(null)

    // 将 isAnimatedBackground 提供给子组件使用
    provide('isAnimatedBackground', isAnimatedBackground)

    // 计算背景内联样式
    const backgroundStyle = computed(() => ({
      position: 'absolute',
      top: '0',
      left: '0',
      width: '100%',
      height: '100%',
      background: 'linear-gradient(-45deg, #ee7752, #e73c7e, #23a6d5, #23d5ab)',
      backgroundSize: '400% 400%',
      opacity: '1',
      transition: 'opacity 0.5s ease',
      animation: 'gradient 15s ease infinite',
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
            console.log('本地有Token和用户，尝试调用/api/auth/me验证...');
            try {
              await axiosInstance.get('/api/auth/me');
              console.log('Token验证成功 (通过/api/auth/me)');
              isAuthenticated = true; // 验证成功！
            } catch (apiError) {
              console.error('/api/auth/me验证失败:', apiError.message);
              // 401错误会被响应拦截器处理（清除Token, 跳转）
              if (apiError.response && apiError.response.status !== 401) {
                console.log('/api/auth/me返回非401错误，视为未认证');
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
    
    // 处理场站切换
    const handleFarmChanged = (farmCode) => {
      console.log(`场站已切换到: ${farmCode}`)

      // 使用farmService进行全局状态管理
      farmService.setCurrentFarm(farmCode)

      // 可以在这里添加其他全局逻辑
      // 例如：更新Axios请求头、触发全局事件等

      // 当前页面的刷新逻辑可以通过子组件处理
      // 或者在这里触发路由重新加载
      if (router.currentRoute.value.path !== '/') {
        // 如果不在首页，可以选择刷新当前页面数据
        // 这里可以添加具体的业务逻辑
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
      handleFarmChanged,
      hasPermission,
      isAuthReady, // 暴露认证状态
      isAuthLoading // 暴露认证加载状态
    }
  },
}
</script>

<style scoped>
/* 主容器 */
.app-container {
  height: 100vh;
  position: relative;
}

/* 对话框样式 */
.dialog-footer {
  text-align: right;
  margin-top: 20px;
}

.custom-form :deep(.el-form-item__content) {
  flex-wrap: nowrap;
  justify-content: flex-start;
}

/* 背景容器 */
.background-container {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
}

/* 定义渐变动画 */
@keyframes gradient {
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

/* 确保其他内容在背景之上 */
.main-container, .sidebar {
  position: relative;
  z-index: 1;
}

/* 调整主容器背景为透明 */
.main-container {
  background: transparent !important;
}

/* 调整主内容区域背景为透明 */
.main-content {
  background: transparent !important;
  padding: 0;
  overflow-y: auto;
}

/* 侧边栏和顶部导航栏 */
.sidebar {
  background: var(--card-dark);
  border-right: 1px solid var(--border-color);
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  z-index: 1000;
  box-shadow: 4px 0 8px rgba(0, 0, 0, 0.05);
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
  transition: all 0.3s ease;
}

.collapse-icon {
  font-size: 24px;
  color: #ffffff;
}

/* 菜单样式 */
.el-menu-vertical {
  border-right: none;
  background: transparent;
  border: none;
}

.el-menu {
  background: transparent;
  border: none;
}

.el-menu-item {
  color: var(--text-secondary);
  height: 50px;
  margin: 8px 0;
}

.el-menu-item.is-active {
  background: linear-gradient(90deg, rgba(52, 199, 89, 0.1), transparent);
  color: #34C759;
  border-left: 3px solid #34C759;
}

.el-menu-item:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #ffffff;
}

.el-menu-item .el-icon {
  font-size: 20px;
}

/* 顶部导航栏 */
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

.header-left {
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
  letter-spacing: -0.003em;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
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
  background: rgba(0, 0, 0, 0.05);
}

.username {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

/* 响应式 */
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

  .username {
    display: none;
  }
}

/* 认证加载指示器样式 */
.auth-loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
}

.auth-loading-container {
  background-color: white;
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
  color: #409EFF;
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
</style>
