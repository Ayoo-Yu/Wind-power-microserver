<template>
  <div class="login-shell">
    <section class="login-visual">
      <div class="texture-grid"></div>
      <div class="texture-lines"></div>
      <div class="particle-layer">
        <span class="particle p1"></span>
        <span class="particle p2"></span>
        <span class="particle p3"></span>
        <span class="particle p4"></span>
        <span class="particle p5"></span>
      </div>
      <div class="turbine-watermark" aria-hidden="true"></div>
      <div class="visual-overlay">
        <h1>风电功率预测系统</h1>
        <p>智慧能源 · 实时感知 · 智能决策</p>
        <ul class="visual-metrics">
          <li>
            <span class="metric-label"><el-icon><OfficeBuilding /></el-icon>场站接入</span>
            <strong>24</strong>
            <i class="metric-line"></i>
          </li>
          <li>
            <span class="metric-label"><el-icon><Lightning /></el-icon>实时总功率</span>
            <strong>1,286 MW</strong>
            <i class="metric-line"></i>
          </li>
          <li>
            <span class="metric-label"><el-icon><Aim /></el-icon>今日预测准确率</span>
            <strong>96.2%</strong>
            <i class="metric-line"></i>
          </li>
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
        <div class="form-meta">
          <label class="remember-row">
            <input v-model="rememberMe" type="checkbox" />
            <span>记住账号</span>
          </label>
          <a href="#" class="helper-link" @click.prevent>联系管理员</a>
        </div>

        <div class="footer">© 2026 中国三峡集团 风电功率预测系统</div>
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
import { User, Lock, OfficeBuilding, Lightning, Aim } from '@element-plus/icons-vue'
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
    const rememberMe = ref(true)
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
      rememberMe,
      User,
      Lock,
      OfficeBuilding,
      Lightning,
      Aim
    }
  }
}
</script>

<style scoped>
.login-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  background:
    radial-gradient(circle at 15% 12%, rgba(30, 88, 130, 0.4) 0%, rgba(8, 26, 43, 0) 40%),
    radial-gradient(circle at 80% 15%, rgba(16, 76, 118, 0.28) 0%, rgba(8, 26, 43, 0) 32%),
    linear-gradient(140deg, #04101c 0%, #071a2c 55%, #050f1a 100%);
}

.login-visual {
  position: relative;
  overflow: hidden;
  padding: 48px;
}

.texture-grid,
.texture-lines,
.particle-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.texture-grid {
  opacity: .2;
  background:
    linear-gradient(rgba(124, 178, 214, .08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(124, 178, 214, .08) 1px, transparent 1px);
  background-size: 28px 28px;
}

.texture-lines {
  opacity: .18;
  background:
    repeating-linear-gradient(120deg, rgba(18, 215, 255, .12) 0, rgba(18, 215, 255, .12) 1px, transparent 1px, transparent 90px);
  animation: drift 18s linear infinite;
}

.particle {
  position: absolute;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: rgba(120, 223, 255, 0.65);
  box-shadow: 0 0 12px rgba(120, 223, 255, 0.58);
  animation: particleFloat 9s ease-in-out infinite;
}

.p1 { left: 12%; top: 20%; animation-delay: 0s; }
.p2 { left: 32%; top: 65%; animation-delay: 1.3s; }
.p3 { left: 48%; top: 30%; animation-delay: 2.6s; }
.p4 { left: 62%; top: 78%; animation-delay: 3.1s; }
.p5 { left: 82%; top: 26%; animation-delay: 4.4s; }

.turbine-watermark {
  position: absolute;
  left: 32%;
  top: 46%;
  width: 420px;
  height: 420px;
  transform: translate(-50%, -50%);
  opacity: .06;
  pointer-events: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'%3E%3Cg fill='none' stroke='%239ad6ff' stroke-width='2.2'%3E%3Cline x1='100' y1='74' x2='100' y2='188'/%3E%3Ccircle cx='100' cy='72' r='8'/%3E%3Cpath d='M100 72L164 48'/%3E%3Cpath d='M100 72L57 11'/%3E%3Cpath d='M100 72L50 117'/%3E%3C/g%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-size: contain;
}

.visual-overlay {
  position: relative;
  z-index: 2;
  max-width: 560px;
  margin: 52px 0 0 58px;
}

.visual-overlay h1 {
  font-size: 44px;
  margin: 0;
  letter-spacing: .8px;
  background: linear-gradient(180deg, #f6fbff 8%, #b8dfff 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  text-shadow: 0 0 18px rgba(116, 194, 255, .12);
}

.visual-overlay p {
  margin-top: 12px;
  color: #deefff;
  letter-spacing: 2.8px;
  font-size: 14px;
}

.visual-metrics {
  list-style: none;
  padding: 0;
  margin: 34px 0 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.visual-metrics li {
  width: 320px;
  padding: 12px 14px;
  border: 1px solid rgba(132, 191, 231, .24);
  border-radius: 12px;
  background: rgba(255, 255, 255, .03);
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  position: relative;
  box-shadow: inset 0 0 0 1px rgba(18, 215, 255, .08);
}

.visual-metrics strong {
  font-family: "Consolas", monospace;
  color: #53f0b0;
  font-size: 24px;
  line-height: 1;
  text-shadow: 0 0 10px rgba(83, 240, 176, .42);
}

.metric-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #a9c7de;
  font-size: 13px;
}

.metric-label .el-icon {
  color: #3ce5ff;
  filter: drop-shadow(0 0 8px rgba(60, 229, 255, .35));
  animation: iconBob 4.8s ease-in-out infinite;
}

.visual-metrics li:nth-child(2) .metric-label .el-icon { animation-delay: .8s; }
.visual-metrics li:nth-child(3) .metric-label .el-icon { animation-delay: 1.6s; }

.metric-line {
  position: absolute;
  left: 14px;
  right: 14px;
  bottom: 8px;
  height: 1px;
  background: linear-gradient(90deg, rgba(18, 215, 255, .1), rgba(83, 240, 176, .5), rgba(18, 215, 255, .1));
}

.wind-scene {
  position: absolute;
  inset: 0;
  opacity: .34;
  background:
    linear-gradient(180deg, rgba(4, 12, 20, 0) 0%, rgba(4, 12, 20, .78) 100%),
    radial-gradient(circle at 58% 82%, rgba(18, 215, 255, .24), transparent 42%),
    repeating-radial-gradient(circle at 80% 90%, rgba(164, 209, 239, .08) 0, rgba(164, 209, 239, .08) 2px, transparent 3px, transparent 16px),
    linear-gradient(0deg, rgba(8, 18, 30, .92), rgba(8, 18, 30, .3));
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
  border: 1px solid rgba(163, 205, 235, .28);
  background: rgba(255, 255, 255, 0.055);
  backdrop-filter: blur(10px);
  box-shadow: 0 20px 46px rgba(0, 0, 0, .35), inset 0 1px 0 rgba(255, 255, 255, .08);
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

.login-form :deep(.el-input__wrapper) {
  background: rgba(12, 38, 58, .88) !important;
  border: 1px solid rgba(88, 186, 235, .24);
  box-shadow: none !important;
  border-radius: 8px;
}

.login-form :deep(.el-input__inner),
.login-form :deep(.el-input__prefix-inner .el-icon) {
  color: #d7ebff !important;
}

.login-form :deep(.el-input__wrapper.is-focus) {
  border-color: rgba(32, 229, 255, .86) !important;
  box-shadow: 0 0 0 1px rgba(32, 229, 255, .35), 0 0 16px rgba(18, 215, 255, .22) !important;
}

.login-button {
  width: 100%;
  height: 42px;
  border-radius: 22px;
  border: none !important;
  background: linear-gradient(90deg, #0a96b5, #19dfff) !important;
  box-shadow: 0 0 0 rgba(18, 215, 255, 0), 0 0 20px rgba(18, 215, 255, .35);
  transition: all .25s ease;
}

.login-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 0 0 rgba(18, 215, 255, 0), 0 0 28px rgba(18, 215, 255, .48);
}

.form-meta {
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #a8c6dc;
  font-size: 12px;
}

.remember-row {
  display: inline-flex;
  gap: 6px;
  align-items: center;
}

.remember-row input {
  accent-color: #12d7ff;
}

.helper-link {
  color: #9fd5f7;
  text-decoration: none;
}

.helper-link:hover {
  color: #c4e7ff;
}

.footer {
  margin-top: 10px;
  font-size: 12px;
  color: #8ba8be;
  text-align: center;
}

@keyframes drift {
  from { transform: translateX(0); }
  to { transform: translateX(-90px); }
}

@keyframes particleFloat {
  0%, 100% { transform: translateY(0px) scale(1); opacity: .52; }
  50% { transform: translateY(-12px) scale(1.12); opacity: .92; }
}

@keyframes iconBob {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-3px); }
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

  .visual-overlay {
    margin: 12px 0 0 0;
  }

  .turbine-watermark {
    left: 50%;
    top: 55%;
    width: 280px;
    height: 280px;
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
