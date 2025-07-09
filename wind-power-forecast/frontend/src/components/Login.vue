<template>
  <div class="login-container">
    <div class="background-container">
      <div class="background-animation"></div>
    </div>
    
    <div class="login-card">
      <div class="logo-container">
        <img src="@/assets/Hust_logo.png" alt="Logo" class="logo" />
        <h1 class="system-title">风电功率预测平台</h1>
      </div>
      
      <el-form 
        ref="loginForm" 
        :model="formData" 
        :rules="loginRules" 
        class="login-form"
      >
        <h2 class="login-title">用户登录</h2>
        
        <el-form-item prop="username">
          <el-input
            v-model="formData.username"
            placeholder="用户名"
            :prefix-icon="User"
          />
        </el-form-item>
        
        <el-form-item prop="password">
          <el-input
            v-model="formData.password"
            type="password"
            placeholder="密码"
            :prefix-icon="Lock"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        
        <el-form-item>
          <el-button 
            type="primary" 
            class="login-button" 
            :loading="loading"
            @click="handleLogin"
          >
            登录
          </el-button>
        </el-form-item>
      </el-form>
      
      <div class="login-footer">
        <p>© 2025 华中科技大学. 版权所有.</p>
      </div>
    </div>
    
    <!-- 首次登录修改密码对话框 -->
    <el-dialog
      v-model="showChangePasswordDialog"
      title="首次登录修改密码"
      width="400px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="false"
    >
      <el-form 
        ref="passwordForm" 
        :model="passwordData" 
        :rules="passwordRules" 
        label-width="100px"
      >
        <el-form-item label="新密码" prop="newPassword">
          <el-input
            v-model="passwordData.newPassword"
            type="password"
            placeholder="请输入新密码"
            show-password
          />
        </el-form-item>
        
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="passwordData.confirmPassword"
            type="password"
            placeholder="请再次输入新密码"
            show-password
          />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button 
          type="primary" 
          :loading="changingPassword"
          @click="handleChangePassword"
        >
          确认修改
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { login, changePassword } from '../api/auth'
import { isAuthReady, isAuthLoading } from '../store/authReady' // 导入认证状态

export default {
  name: 'LoginView',
  setup() {
    const router = useRouter()
    const loginForm = ref(null)
    const passwordForm = ref(null)
    
    const formData = reactive({
      username: '',
      password: ''
    })
    
    const passwordData = reactive({
      newPassword: '',
      confirmPassword: ''
    })
    
    const loading = ref(false)
    const changingPassword = ref(false)
    const showChangePasswordDialog = ref(false)
    
    // 登录表单验证规则
    const loginRules = {
      username: [
        { required: true, message: '请输入用户名', trigger: 'blur' }
      ],
      password: [
        { required: true, message: '请输入密码', trigger: 'blur' }
      ]
    }
    
    // 密码表单验证规则
    const passwordRules = {
      newPassword: [
        { required: true, message: '请输入新密码', trigger: 'blur' },
        { min: 6, message: '密码长度不能少于6个字符', trigger: 'blur' }
      ],
      confirmPassword: [
        { required: true, message: '请再次输入新密码', trigger: 'blur' },
        {
          validator: (rule, value, callback) => {
            if (value !== passwordData.newPassword) {
              callback(new Error('两次输入的密码不一致'))
            } else {
              callback()
            }
          },
          trigger: 'blur'
        }
      ]
    }
    
    // 处理登录
    const handleLogin = async () => {
      if (!loginForm.value) return
      
      await loginForm.value.validate(async (valid) => {
        if (!valid) return
        
        loading.value = true
        
        try {
          // 先清除本地存储和认证状态，确保获取最新权限
          localStorage.removeItem('user');
          localStorage.removeItem('accessToken');
          isAuthReady.value = false; // 重置认证状态
          isAuthLoading.value = true; // 标记为正在加载状态
          
          const userData = await login(formData.username, formData.password)
          
          // 存储用户信息和访问令牌
          localStorage.setItem('user', JSON.stringify(userData.user))
          
          // 存储访问令牌
          if (userData.access_token) {
            localStorage.setItem('accessToken', userData.access_token)
            console.log('访问令牌已存储:', userData.access_token)
            
            // 显示成功消息
            ElMessage.success('登录成功')
            
            // 直接跳转到首页，让AppLayout处理认证状态检查
            router.push('/')
          } else {
            console.warn('登录响应中没有找到访问令牌')
            ElMessage.error('登录异常：服务器未返回访问令牌')
          }
        } catch (error) {
          console.error('登录失败:', error)
          ElMessage.error(error.response?.data?.message || '登录失败，请检查用户名和密码')
          // 确保认证状态重置
          isAuthReady.value = false;
          isAuthLoading.value = false;
        } finally {
          loading.value = false
        }
      })
    }
    
    // 处理修改密码
    const handleChangePassword = async () => {
      if (!passwordForm.value) return
      
      await passwordForm.value.validate(async (valid) => {
        if (!valid) return
        
        changingPassword.value = true
        
        try {
          await changePassword(
            formData.username,
            formData.password,
            passwordData.newPassword
          )
          
          showChangePasswordDialog.value = false
          ElMessage.success('密码修改成功，请使用新密码登录')
          
          // 清除登录信息，重新登录
          localStorage.removeItem('user')
          formData.password = ''
          
          // 跳转到登录页
          router.push('/login')
        } catch (error) {
          console.error('修改密码失败:', error)
          ElMessage.error(error.response?.data?.message || '修改密码失败')
        } finally {
          changingPassword.value = false
        }
      })
    }
    
    return {
      loginForm,
      passwordForm,
      loginRules,
      passwordRules,
      loading,
      changingPassword,
      showChangePasswordDialog,
      handleLogin,
      handleChangePassword,
      formData,
      passwordData,
      User,
      Lock
    }
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  position: relative;
  overflow: hidden;
}

/* 添加全局输入框文字样式，确保在云服务器上可见 */
:deep(.el-input__inner) {
  color: #333 !important; /* 深色文字，确保在白色背景上可见 */
}

.background-container {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
}

.background-animation {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(-45deg, #ee7752, #e73c7e, #23a6d5, #23d5ab);
  background-size: 400% 400%;
  animation: gradient 15s ease infinite;
}

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

.login-card {
  width: 400px;
  padding: 30px;
  background-color: rgba(255, 255, 255, 0.9);
  border-radius: 10px;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.1);
  z-index: 1;
  position: relative;
}

.logo-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 20px;
}

.logo {
  height: 60px;
  margin-bottom: 10px;
}

.system-title {
  font-size: 20px;
  color: #333;
  text-align: center;
  margin: 0;
}

.login-title {
  font-size: 24px;
  color: #333;
  text-align: center;
  margin-bottom: 30px;
}

.login-form {
  margin-bottom: 20px;
}

.login-button {
  width: 100%;
  padding: 12px 0;
  font-size: 16px;
}

.login-footer {
  text-align: center;
  color: #666;
  font-size: 12px;
  margin-top: 20px;
}
</style> 