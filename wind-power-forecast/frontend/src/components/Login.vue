<template>
  <div class="login-shell">
    <section class="login-visual">
      <div class="visual-overlay">
        <h1>风电功率预测系统</h1>
        <p>智慧能源 · 实时感知 · 智能决策</p>
        <ul class="visual-metrics">
          <li><span>场站接入</span><strong>24</strong></li>
          <li><span>实时总功率</span><strong>1,286 MW</strong></li>
          <li><span>今日预测准确率</span><strong>96.2%</strong></li>
        </ul>
      </div>
      <div class="wind-scene" />
    </section>

    <section class="login-panel">
      <div class="login-card">
        <div class="logo-line">
          <img src="@/assets/Sanxia_logo_black.png" alt="logo" class="logo" />
          <h2>用户登录</h2>
        </div>

        <el-form ref="loginForm" :model="formData" :rules="loginRules" class="login-form">
          <el-form-item prop="username">
            <el-input v-model="formData.username" placeholder="请输入用户名" :prefix-icon="User" />
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="formData.password"
              type="password"
              placeholder="请输入密码"
              :prefix-icon="Lock"
              show-password
              @keyup.enter="handleLogin"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" class="login-button" :loading="loading" @click="handleLogin">登录</el-button>
          </el-form-item>
        </el-form>

        <div class="footer">? 2026 中国三峡集团 风电功率预测系统</div>
      </div>
    </section>

    <el-dialog
      v-model="showChangePasswordDialog"
      title="首次登录请修改密码"
      width="420px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="false"
    >
      <el-form ref="passwordForm" :model="passwordData" :rules="passwordRules" label-width="100px">
        <el-form-item label="新密码" prop="newPassword">
          <el-input v-model="passwordData.newPassword" type="password" placeholder="请输入新密码" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input v-model="passwordData.confirmPassword" type="password" placeholder="请再次输入新密码" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" :loading="changingPassword" @click="handleChangePassword">确认修改</el-button>
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
import { isAuthReady, isAuthLoading } from '../store/authReady'

export default {
  name: 'LoginView',
  setup() {
    const router = useRouter()
    const loginForm = ref(null)
    const passwordForm = ref(null)

    const formData = reactive({ username: '', password: '' })
    const passwordData = reactive({ newPassword: '', confirmPassword: '' })
    const loading = ref(false)
    const changingPassword = ref(false)
    const showChangePasswordDialog = ref(false)

    const loginRules = {
      username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
      password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
    }

    const passwordRules = {
      newPassword: [
        { required: true, message: '请输入新密码', trigger: 'blur' },
        { min: 6, message: '密码长度不少于 6 位', trigger: 'blur' }
      ],
      confirmPassword: [
        { required: true, message: '请再次输入新密码', trigger: 'blur' },
        {
          validator: (rule, value, callback) => {
            if (value !== passwordData.newPassword) callback(new Error('两次输入密码不一致'))
            else callback()
          },
          trigger: 'blur'
        }
      ]
    }

    const handleLogin = async () => {
      if (!loginForm.value) return
      await loginForm.value.validate(async (valid) => {
        if (!valid) return
        loading.value = true
        try {
          localStorage.removeItem('user')
          localStorage.removeItem('accessToken')
          isAuthReady.value = false
          isAuthLoading.value = true

          const userData = await login(formData.username, formData.password)
          localStorage.setItem('user', JSON.stringify(userData.user))

          if (userData.access_token) {
            localStorage.setItem('accessToken', userData.access_token)
            ElMessage.success('登录成功')
            router.push('/')
          } else {
            ElMessage.error('登录异常：服务端未返回访问令牌')
          }
        } catch (error) {
          ElMessage.error(error.response?.data?.message || '登录失败，请检查用户名和密码')
          isAuthReady.value = false
          isAuthLoading.value = false
        } finally {
          loading.value = false
        }
      })
    }

    const handleChangePassword = async () => {
      if (!passwordForm.value) return
      await passwordForm.value.validate(async (valid) => {
        if (!valid) return
        changingPassword.value = true
        try {
          await changePassword(formData.username, formData.password, passwordData.newPassword)
          showChangePasswordDialog.value = false
          ElMessage.success('密码修改成功，请重新登录')
          localStorage.removeItem('user')
          formData.password = ''
          router.push('/login')
        } catch (error) {
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
.login-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  background: radial-gradient(circle at 10% 10%, #113252 0%, #071727 40%, #06121f 100%);
}

.login-visual {
  position: relative;
  overflow: hidden;
  padding: 48px;
}

.visual-overlay {
  position: relative;
  z-index: 2;
}

.visual-overlay h1 {
  font-size: 40px;
  margin: 0;
}

.visual-overlay p {
  margin-top: 12px;
  color: #a5c3db;
}

.visual-metrics {
  list-style: none;
  padding: 0;
  margin: 28px 0 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.visual-metrics li {
  width: 280px;
  padding: 10px 14px;
  border: 1px solid rgba(150, 200, 234, .28);
  border-radius: 10px;
  background: rgba(10, 29, 45, .55);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.visual-metrics strong {
  font-family: "Consolas", monospace;
  color: #12d7ff;
}

.wind-scene {
  position: absolute;
  inset: 0;
  opacity: .28;
  background:
    linear-gradient(180deg, transparent 0%, rgba(6, 18, 31, 0.9) 100%),
    radial-gradient(circle at 60% 80%, rgba(18, 215, 255, .35), transparent 45%),
    repeating-linear-gradient(90deg, rgba(255,255,255,.03) 0, rgba(255,255,255,.03) 1px, transparent 1px, transparent 28px);
}

.login-panel {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 24px;
}

.login-card {
  width: min(420px, 92vw);
  border-radius: 14px;
  padding: 28px;
  border: 1px solid rgba(163, 205, 235, .35);
  background: rgba(13, 36, 54, 0.6);
  backdrop-filter: blur(12px);
  box-shadow: 0 16px 45px rgba(0, 0, 0, .35);
}

.logo-line {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
}

.logo {
  height: 36px;
  filter: grayscale(100%) brightness(1.7);
}

.logo-line h2 {
  margin: 0;
  font-size: 22px;
  color: #eaf4ff;
}

.login-button {
  width: 100%;
  height: 42px;
}

.footer {
  margin-top: 10px;
  font-size: 12px;
  color: #8ba8be;
  text-align: center;
}

@media (max-width: 900px) {
  .login-shell {
    grid-template-columns: 1fr;
  }

  .login-visual {
    min-height: 220px;
    padding: 24px;
  }

  .visual-overlay h1 {
    font-size: 28px;
  }

  .visual-metrics {
    flex-direction: row;
    flex-wrap: wrap;
  }

  .visual-metrics li {
    width: calc(50% - 6px);
  }
}
</style>
