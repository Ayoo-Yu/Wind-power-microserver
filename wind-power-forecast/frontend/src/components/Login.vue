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
      <div class="turbine-watermark turbine-watermark-far" aria-hidden="true"></div>

      <div class="visual-overlay">
        <h1>风电功率预测系统</h1>
        <p>智慧能源 · 实时感知 · 智能决策</p>

        <ul class="visual-metrics">
          <li>
            <span class="metric-label">
              <el-icon><OfficeBuilding /></el-icon>
              <i class="metric-pulse"></i>
              场站接入
            </span>
            <strong class="metric-value metric-mask">{{ maskedMetrics.stationCount }}</strong>
            <i class="metric-line"></i>
          </li>
          <li>
            <span class="metric-label">
              <el-icon><Lightning /></el-icon>
              <i class="metric-pulse"></i>
              实时总功率
            </span>
            <strong class="metric-value">
              {{ maskedMetrics.totalPower }}
            </strong>
            <i class="metric-line"></i>
          </li>
          <li>
            <span class="metric-label">
              <el-icon><Aim /></el-icon>
              <i class="metric-pulse"></i>
              今日预测准确率
            </span>
            <strong class="metric-value metric-mask">{{ maskedMetrics.accuracy }}</strong>
            <i class="metric-line"></i>
          </li>
        </ul>

        <div class="announcement-ticker">
          <span class="ticker-label">系统公告</span>
          <div class="ticker-track">
            <div class="ticker-content">{{ systemNotice }}</div>
          </div>
        </div>
      </div>

      <div class="wind-scene" />
    </section>

    <section class="login-panel">
      <div class="login-card">
        <div class="logo-line">
          <img src="@/assets/Sanxia_logo_black.png" alt="logo" class="logo" />
          <div class="logo-copy">
            <h2>三峡能源</h2>
            <span>风电功率预测平台</span>
          </div>
        </div>

        <div v-if="lockoutMessage" class="security-alert">{{ lockoutMessage }}</div>

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
          <el-form-item prop="captchaInput">
            <div class="captcha-row">
              <el-input
                v-model.trim="formData.captchaInput"
                placeholder="请输入验证码结果"
                :disabled="isLocked"
                @keyup.enter="handleLogin"
              />
              <button type="button" class="captcha-challenge" @click="refreshCaptcha" title="点击刷新验证码">
                {{ captchaText }}
              </button>
            </div>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" class="login-button" :loading="loading" :disabled="isLocked" @click="handleLogin">登录</el-button>
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
        <div class="version">v1.2.4 (Build 20260305)</div>
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
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, OfficeBuilding, Lightning, Aim } from '@element-plus/icons-vue'
import { login, changePassword } from '../api/auth'
import { isAuthReady, isAuthLoading } from '../store/authReady'

export default {
  name: 'LoginView',
  setup() {
    const LOCK_STORAGE_KEY = 'login_security_lock_v1'
    const MAX_FAIL_COUNT = 5
    const LOCK_DURATION_MS = 15 * 60 * 1000

    const router = useRouter()
    const loginForm = ref(null)
    const passwordForm = ref(null)

    const formData = reactive({ username: '', password: '', captchaInput: '' })
    const passwordData = reactive({ newPassword: '', confirmPassword: '' })
    const rememberMe = ref(true)
    const loading = ref(false)
    const changingPassword = ref(false)
    const showChangePasswordDialog = ref(false)
    const nowTs = ref(Date.now())
    const timerId = ref(0)
    const systemNotice = ref('⚠️ 通知：今晚 00:00-01:00 系统进行主备切换演练，期间预测数据可能存在延迟。')
    const captchaText = ref('')
    const captchaAnswer = ref('')
    const lockState = reactive({
      failCount: 0,
      lockedUntil: 0
    })

    const maskedMetrics = reactive({
      stationCount: '----',
      totalPower: '----',
      accuracy: '----'
    })

    const loginRules = {
      username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
      password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
      captchaInput: [{ required: true, message: '请输入验证码', trigger: 'blur' }]
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

    const storageRead = () => {
      try {
        const raw = localStorage.getItem(LOCK_STORAGE_KEY)
        return raw ? JSON.parse(raw) : {}
      } catch (error) {
        return {}
      }
    }

    const storageWrite = (value) => {
      localStorage.setItem(LOCK_STORAGE_KEY, JSON.stringify(value))
    }

    const normalizeUserKey = () => String(formData.username || '__anonymous__').trim().toLowerCase()

    const loadLockState = () => {
      const all = storageRead()
      const current = all[normalizeUserKey()] || {}
      lockState.failCount = Number(current.failCount || 0)
      lockState.lockedUntil = Number(current.lockedUntil || 0)
    }

    const persistLockState = () => {
      const all = storageRead()
      all[normalizeUserKey()] = {
        failCount: lockState.failCount,
        lockedUntil: lockState.lockedUntil
      }
      storageWrite(all)
    }

    const clearLockState = () => {
      lockState.failCount = 0
      lockState.lockedUntil = 0
      persistLockState()
    }

    const recordFailAndMaybeLock = () => {
      lockState.failCount += 1
      if (lockState.failCount >= MAX_FAIL_COUNT) {
        lockState.lockedUntil = Date.now() + LOCK_DURATION_MS
      }
      persistLockState()
    }

    const refreshCaptcha = () => {
      const left = Math.floor(Math.random() * 9) + 1
      const right = Math.floor(Math.random() * 9) + 1
      captchaText.value = `${left} + ${right} = ?`
      captchaAnswer.value = String(left + right)
      formData.captchaInput = ''
    }

    const isLocked = computed(() => lockState.lockedUntil > nowTs.value)

    const lockoutMessage = computed(() => {
      if (!isLocked.value) return ''
      const remainSec = Math.max(0, Math.ceil((lockState.lockedUntil - nowTs.value) / 1000))
      const mm = String(Math.floor(remainSec / 60)).padStart(2, '0')
      const ss = String(remainSec % 60).padStart(2, '0')
      return `密码连续输错 5 次，账号已锁定 15 分钟。剩余 ${mm}:${ss}`
    })

    const handleLogin = async () => {
      if (!loginForm.value) return
      loadLockState()

      if (isLocked.value) {
        ElMessage.error(lockoutMessage.value)
        return
      }

      await loginForm.value.validate(async (valid) => {
        if (!valid) return
        if (String(formData.captchaInput).trim() !== captchaAnswer.value) {
          ElMessage.error('验证码错误，请重新输入')
          refreshCaptcha()
          return
        }
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
            clearLockState()
            ElMessage.success('登录成功')
            router.push('/')
          } else {
            ElMessage.error('登录异常：服务端未返回访问令牌')
          }
        } catch (error) {
          recordFailAndMaybeLock()
          refreshCaptcha()
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

    onMounted(() => {
      refreshCaptcha()
      loadLockState()
      timerId.value = setInterval(() => {
        nowTs.value = Date.now()
      }, 1000)
    })

    watch(() => formData.username, () => {
      loadLockState()
    })

    onBeforeUnmount(() => {
      if (timerId.value) {
        clearInterval(timerId.value)
      }
    })

    return {
      loginForm,
      passwordForm,
      loginRules,
      passwordRules,
      loading,
      changingPassword,
      showChangePasswordDialog,
      isLocked,
      lockoutMessage,
      captchaText,
      refreshCaptcha,
      handleLogin,
      handleChangePassword,
      formData,
      passwordData,
      rememberMe,
      maskedMetrics,
      systemNotice,
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
  position: relative;
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  overflow: hidden;
  background:
    radial-gradient(circle at 15% 12%, rgba(30, 88, 130, 0.4) 0%, rgba(8, 26, 43, 0) 40%),
    radial-gradient(circle at 80% 15%, rgba(16, 76, 118, 0.28) 0%, rgba(8, 26, 43, 0) 32%),
    linear-gradient(140deg, #04101c 0%, #071a2c 55%, #050f1a 100%);
}

.login-shell::before,
.login-shell::after {
  content: '';
  position: absolute;
  width: 620px;
  height: 620px;
  border-radius: 50%;
  pointer-events: none;
  z-index: 0;
}

.login-shell::before {
  left: -220px;
  top: -280px;
  background: radial-gradient(circle, rgba(18, 215, 255, 0.08) 0%, rgba(18, 215, 255, 0) 72%);
}

.login-shell::after {
  right: -260px;
  bottom: -320px;
  background: radial-gradient(circle, rgba(35, 98, 148, 0.14) 0%, rgba(35, 98, 148, 0) 72%);
}

.login-visual {
  position: relative;
  z-index: 1;
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
  opacity: 0.2;
  background:
    linear-gradient(rgba(124, 178, 214, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(124, 178, 214, 0.08) 1px, transparent 1px);
  background-size: 28px 28px;
}

.texture-lines {
  opacity: 0.18;
  background: repeating-linear-gradient(
    120deg,
    rgba(18, 215, 255, 0.12) 0,
    rgba(18, 215, 255, 0.12) 1px,
    transparent 1px,
    transparent 90px
  );
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

.p1 {
  left: 12%;
  top: 20%;
  animation-delay: 0s;
}

.p2 {
  left: 32%;
  top: 65%;
  animation-delay: 1.3s;
}

.p3 {
  left: 48%;
  top: 30%;
  animation-delay: 2.6s;
}

.p4 {
  left: 62%;
  top: 78%;
  animation-delay: 3.1s;
}

.p5 {
  left: 82%;
  top: 26%;
  animation-delay: 4.4s;
}

.turbine-watermark {
  position: absolute;
  left: 48%;
  top: 50%;
  width: 500px;
  height: 500px;
  transform: translate(-50%, -50%);
  opacity: 0.08;
  pointer-events: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'%3E%3Cg fill='none' stroke='%239ad6ff' stroke-width='2.2'%3E%3Cline x1='100' y1='74' x2='100' y2='188'/%3E%3Ccircle cx='100' cy='72' r='8'/%3E%3Cpath d='M100 72L164 48'/%3E%3Cpath d='M100 72L57 11'/%3E%3Cpath d='M100 72L50 117'/%3E%3C/g%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-size: contain;
}

.turbine-watermark-far {
  left: 74%;
  top: 60%;
  width: 260px;
  height: 260px;
  opacity: 0.035;
}

.visual-overlay {
  position: relative;
  z-index: 2;
  max-width: 560px;
  margin: 52px 0 0 58px;
}

.visual-overlay h1 {
  margin: 0;
  font-size: 46px;
  font-weight: 800;
  letter-spacing: 1px;
  background: linear-gradient(180deg, #f6fbff 8%, #b8dfff 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  text-shadow: 0 0 18px rgba(116, 194, 255, 0.12);
}

.visual-overlay p {
  margin-top: 12px;
  color: #e7f2ff;
  letter-spacing: 3px;
  font-size: 14px;
}

.visual-metrics {
  list-style: none;
  padding: 0;
  margin: 34px 0 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.visual-metrics li {
  width: 344px;
  padding: 14px 16px 16px;
  border: 1px solid rgba(132, 191, 231, 0.24);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.035);
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: relative;
  box-shadow: inset 0 0 0 1px rgba(18, 215, 255, 0.08);
}

.metric-label {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #a9c7de;
  font-size: 13px;
}

.metric-pulse {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #38e0ff;
  box-shadow: 0 0 10px rgba(56, 224, 255, 0.75);
  animation: pulse 2.6s ease-in-out infinite;
}

.metric-label .el-icon {
  color: #3ce5ff;
  filter: drop-shadow(0 0 8px rgba(60, 229, 255, 0.35));
  animation: iconBob 4.8s ease-in-out infinite;
}

.visual-metrics li:nth-child(2) .metric-label .el-icon,
.visual-metrics li:nth-child(2) .metric-pulse {
  animation-delay: 0.8s;
}

.visual-metrics li:nth-child(3) .metric-label .el-icon,
.visual-metrics li:nth-child(3) .metric-pulse {
  animation-delay: 1.6s;
}

.metric-value {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  font-family: Consolas, Menlo, Monaco, monospace;
  color: #53f0b0;
  font-size: 24px;
  line-height: 1;
  text-shadow: 0 0 10px rgba(83, 240, 176, 0.42);
}

.metric-unit {
  color: #8dcbb0;
  font-size: 14px;
  letter-spacing: 0.4px;
}

.metric-line {
  position: absolute;
  left: 16px;
  right: 16px;
  bottom: 8px;
  height: 1px;
  background: linear-gradient(90deg, rgba(18, 215, 255, 0.1), rgba(83, 240, 176, 0.5), rgba(18, 215, 255, 0.1));
}

.wind-scene {
  position: absolute;
  inset: 0;
  opacity: 0.34;
  background:
    linear-gradient(180deg, rgba(4, 12, 20, 0) 0%, rgba(4, 12, 20, 0.78) 100%),
    radial-gradient(circle at 58% 82%, rgba(18, 215, 255, 0.24), transparent 42%),
    repeating-radial-gradient(circle at 80% 90%, rgba(164, 209, 239, 0.08) 0, rgba(164, 209, 239, 0.08) 2px, transparent 3px, transparent 16px),
    linear-gradient(0deg, rgba(8, 18, 30, 0.92), rgba(8, 18, 30, 0.3));
}

.login-panel {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 24px;
}

.login-card {
  width: min(420px, 92vw);
  border-radius: 14px;
  padding: 28px;
  border: 1px solid rgba(163, 205, 235, 0.28);
  background: rgba(255, 255, 255, 0.055);
  backdrop-filter: blur(10px);
  box-shadow: 0 20px 46px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.logo-line {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 18px;
}

.logo {
  height: 38px;
  filter: grayscale(100%) brightness(2.15) contrast(1.08) drop-shadow(0 0 6px rgba(199, 236, 255, 0.2));
}

.logo-copy {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.logo-copy h2 {
  margin: 0;
  font-size: 22px;
  color: #eef7ff;
  letter-spacing: 0.6px;
}

.logo-copy span {
  font-size: 12px;
  letter-spacing: 1px;
  color: #a8c7df;
}

.security-alert {
  margin: 4px 0 12px;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid rgba(255, 102, 102, 0.45);
  background: rgba(120, 16, 16, 0.26);
  color: #ff8787;
  font-size: 12px;
}

.login-form :deep(.el-input__wrapper) {
  background: rgba(7, 26, 42, 0.72) !important;
  border: 1px solid rgba(107, 188, 230, 0.3);
  box-shadow: none !important;
  border-radius: 8px;
}

.login-form :deep(.el-input__inner) {
  color: #e9f7ff !important;
}

.login-form :deep(.el-input__inner::placeholder) {
  color: #9ec4da !important;
}

.login-form :deep(.el-input__prefix-inner .el-icon),
.login-form :deep(.el-input__suffix-inner .el-icon) {
  color: #b8d8ea !important;
}

.login-form :deep(.el-input__wrapper.is-focus) {
  border-color: rgba(64, 235, 255, 0.92) !important;
  box-shadow: 0 0 0 1px rgba(47, 220, 255, 0.42), 0 0 22px rgba(18, 215, 255, 0.38) !important;
}

.captcha-row {
  width: 100%;
  display: grid;
  grid-template-columns: 1fr 128px;
  gap: 8px;
}

.captcha-challenge {
  border: 1px solid rgba(99, 176, 216, 0.36);
  background: rgba(9, 32, 50, 0.8);
  color: #d7ebf9;
  border-radius: 8px;
  font-family: Consolas, Menlo, Monaco, monospace;
  cursor: pointer;
  transition: all 0.2s ease;
}

.captcha-challenge:hover {
  border-color: rgba(64, 235, 255, 0.92);
  box-shadow: 0 0 12px rgba(18, 215, 255, 0.25);
}

.login-button {
  width: 100%;
  height: 42px;
  border-radius: 22px;
  border: none !important;
  background: linear-gradient(90deg, #0a96b5, #19dfff) !important;
  box-shadow: 0 0 0 rgba(18, 215, 255, 0), 0 0 20px rgba(18, 215, 255, 0.35);
  transition: all 0.25s ease;
}

.login-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 0 0 rgba(18, 215, 255, 0), 0 0 28px rgba(18, 215, 255, 0.48);
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

.version {
  margin-top: 4px;
  font-size: 11px;
  color: rgba(156, 178, 194, 0.8);
  text-align: right;
}

.metric-mask {
  position: relative;
  color: rgba(197, 220, 236, 0.85);
  letter-spacing: 2px;
}

.metric-mask::after {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: 4px;
  background: linear-gradient(90deg, transparent, rgba(18, 215, 255, 0.24), transparent);
  animation: shimmer 1.8s linear infinite;
}

.announcement-ticker {
  width: 344px;
  margin-top: 16px;
  display: grid;
  grid-template-columns: 66px 1fr;
  gap: 8px;
  align-items: center;
}

.ticker-label {
  color: #fbbf24;
  font-size: 12px;
}

.ticker-track {
  overflow: hidden;
  border: 1px solid rgba(132, 191, 231, 0.28);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.05);
  height: 30px;
  display: flex;
  align-items: center;
}

.ticker-content {
  white-space: nowrap;
  color: #cce4f7;
  font-size: 12px;
  padding-left: 100%;
  animation: tickerMove 14s linear infinite;
}

@keyframes drift {
  from {
    transform: translateX(0);
  }

  to {
    transform: translateX(-90px);
  }
}

@keyframes particleFloat {
  0%,
  100% {
    transform: translateY(0) scale(1);
    opacity: 0.52;
  }

  50% {
    transform: translateY(-12px) scale(1.12);
    opacity: 0.92;
  }
}

@keyframes iconBob {
  0%,
  100% {
    transform: translateY(0);
  }

  50% {
    transform: translateY(-3px);
  }
}

@keyframes pulse {
  0%,
  100% {
    opacity: 0.5;
    transform: scale(1);
  }

  50% {
    opacity: 1;
    transform: scale(1.15);
  }
}

@keyframes shimmer {
  from {
    transform: translateX(-100%);
  }
  to {
    transform: translateX(100%);
  }
}

@keyframes tickerMove {
  from {
    transform: translateX(0);
  }
  to {
    transform: translateX(-100%);
  }
}

@media (max-width: 900px) {
  .login-shell {
    grid-template-columns: 1fr;
  }

  .login-visual {
    min-height: 220px;
    padding: 24px;
  }

  .visual-overlay {
    margin: 12px 0 0;
  }

  .visual-overlay h1 {
    font-size: 28px;
  }

  .turbine-watermark {
    left: 50%;
    top: 55%;
    width: 320px;
    height: 320px;
  }

  .turbine-watermark-far {
    display: none;
  }

  .visual-metrics {
    flex-direction: row;
    flex-wrap: wrap;
  }

  .visual-metrics li {
    width: calc(50% - 7px);
  }
}
</style>
