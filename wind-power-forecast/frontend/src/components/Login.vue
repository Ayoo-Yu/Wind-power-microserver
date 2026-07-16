<template>
  <div class="login-shell">
    <section class="visual-panel" aria-label="风电预测平台介绍">
      <div class="visual-brand">
        <img src="@/assets/Hust_logo.png" alt="华中科技大学" />
        <div>
          <strong>风电功率预测系统</strong>
          <span>华中科技大学</span>
        </div>
      </div>

      <div class="visual-copy">
        <span class="visual-kicker">风场预测工作台</span>
        <h1>让每一次预测<br />更接近风的真实轨迹</h1>
        <p>汇集场站实况、数值天气预报与模型运行状态，为预测人员提供清晰、可靠的日常工作界面。</p>
        <div class="visual-capabilities" aria-label="平台核心能力">
          <span>SCADA 实时链路</span>
          <span>NWP 数据接入</span>
          <span>多尺度功率预测</span>
        </div>
      </div>

      <div class="visual-caption">
        <strong>面向风电场站的预测运行与质量管理</strong>
        <span>数据状态、预测任务和考核结果统一呈现</span>
      </div>
    </section>

    <section class="login-panel">
      <div class="login-card">
        <div class="mobile-brand">
          <img src="@/assets/Hust_logo.png" alt="华中科技大学" />
          <strong>风电功率预测系统</strong>
        </div>

        <div class="login-heading">
          <span>安全登录</span>
          <h2>欢迎回来</h2>
          <p>登录后进入当前场站的预测运行工作台。</p>
        </div>

        <div v-if="lockoutMessage" class="security-alert" role="alert">{{ lockoutMessage }}</div>

        <el-form
          ref="loginForm"
          :model="formData"
          :rules="loginRules"
          label-position="top"
          class="login-form"
        >
          <el-form-item label="账号" prop="username">
            <el-input
              v-model="formData.username"
              autocomplete="username"
              placeholder="请输入用户名"
              :prefix-icon="User"
            />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input
              v-model="formData.password"
              type="password"
              autocomplete="current-password"
              placeholder="请输入密码"
              :prefix-icon="Lock"
              show-password
              @keyup.enter="handleLogin"
            />
          </el-form-item>
          <el-form-item label="安全验证" prop="captchaInput">
            <div class="captcha-row">
              <el-input
                v-model.trim="formData.captchaInput"
                inputmode="numeric"
                placeholder="请输入计算结果"
                :disabled="isLocked"
                @keyup.enter="handleLogin"
              />
              <button type="button" class="captcha-challenge" @click="refreshCaptcha" title="点击刷新验证码">
                {{ captchaText }}
              </button>
            </div>
          </el-form-item>
          <el-form-item class="submit-item">
            <el-button
              type="primary"
              class="login-button"
              :loading="loading"
              :disabled="isLocked"
              @click="handleLogin"
            >
              进入预测平台
            </el-button>
          </el-form-item>
        </el-form>

        <div class="form-meta">
          <label class="remember-row">
            <input v-model="rememberMe" type="checkbox" />
            <span>记住账号</span>
          </label>
          <span class="helper-text">账号问题请联系系统管理员</span>
        </div>

        <div class="login-footer">
          <span>© 2026 华中科技大学</span>
          <span>v1.2.4</span>
        </div>
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
import { User, Lock } from '@element-plus/icons-vue'
import { login, changePassword, getCurrentUser } from '../api/auth'
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
    const captchaText = ref('')
    const captchaAnswer = ref('')
    const lockState = reactive({
      failCount: 0,
      lockedUntil: 0
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
      } catch {
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

          if (userData.access_token) {
            localStorage.setItem('accessToken', userData.access_token)
            const currentUser = await getCurrentUser()
            localStorage.setItem('user', JSON.stringify(currentUser))
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
      User,
      Lock
    }
  }
}
</script>

<style scoped>
.login-shell {
  min-height: 100dvh;
  display: grid;
  grid-template-columns: minmax(0, 1.18fr) minmax(430px, 0.82fr);
  overflow: hidden;
  background: #ffffff;
}

.visual-panel {
  min-height: 100dvh;
  position: relative;
  display: flex;
  flex-direction: column;
  padding: 38px 48px 34px;
  background-color: #f7f8f4;
  background-image: url('@/assets/wind-farm-hero.webp');
  background-repeat: no-repeat;
  background-position: right bottom;
  background-size: auto 68%;
  border-right: 1px solid var(--border-color);
}

.visual-brand,
.mobile-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.visual-brand img,
.mobile-brand img {
  width: 42px;
  height: 42px;
  object-fit: contain;
}

.visual-brand div {
  display: grid;
  gap: 2px;
}

.visual-brand strong,
.mobile-brand strong {
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 680;
}

.visual-brand span {
  color: var(--text-muted);
  font-size: 12px;
}

.visual-copy {
  max-width: 540px;
  margin-top: clamp(72px, 13vh, 132px);
}

.visual-kicker,
.login-heading > span {
  display: inline-block;
  color: var(--accent);
  font-size: 12px;
  font-weight: 650;
  letter-spacing: 0.12em;
}

.visual-copy h1 {
  margin: 18px 0 18px;
  color: #18231c;
  font-size: clamp(40px, 4vw, 62px);
  font-weight: 680;
  line-height: 1.12;
  letter-spacing: -0.04em;
}

.visual-copy p {
  max-width: 500px;
  margin: 0;
  color: #59645d;
  font-size: 16px;
  line-height: 1.85;
}

.visual-capabilities {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 22px;
  margin-top: 28px;
  padding-top: 20px;
  border-top: 1px solid rgba(52, 77, 61, 0.14);
  color: #425148;
  font-size: 13px;
  font-weight: 560;
}

.visual-caption {
  display: grid;
  gap: 5px;
  margin-top: auto;
  padding-top: 28px;
}

.visual-caption strong {
  color: #26352c;
  font-size: 14px;
}

.visual-caption span {
  color: #6d7871;
  font-size: 12px;
}

.login-panel {
  min-height: 100dvh;
  display: grid;
  place-items: center;
  padding: 44px clamp(36px, 6vw, 92px);
  background: #ffffff;
}

.login-card {
  width: min(420px, 100%);
}

.mobile-brand {
  display: none;
  margin-bottom: 42px;
}

.login-heading {
  margin-bottom: 30px;
}

.login-heading h2 {
  margin: 12px 0 8px;
  color: var(--text-primary);
  font-size: 34px;
  font-weight: 680;
  line-height: 1.2;
  letter-spacing: -0.03em;
}

.login-heading p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.7;
}

.security-alert {
  margin-bottom: 18px;
  padding: 11px 13px;
  color: #a64343;
  background: var(--danger-soft);
  border: 1px solid #edc9c9;
  border-radius: 9px;
  font-size: 13px;
  line-height: 1.5;
}

.login-form :deep(.el-form-item) {
  margin-bottom: 20px;
}

.login-form :deep(.el-form-item__label) {
  height: auto;
  margin-bottom: 8px;
  padding: 0;
  color: #344039 !important;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
}

.login-form :deep(.el-input__wrapper) {
  min-height: 46px;
  padding: 0 13px;
  border-radius: 9px;
}

.login-form :deep(.el-input__prefix-inner .el-icon),
.login-form :deep(.el-input__suffix-inner .el-icon) {
  color: #7b8780;
}

.captcha-row {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 126px;
  gap: 10px;
}

.captcha-challenge {
  min-height: 46px;
  color: #344039;
  background: #f7f9f7;
  border: 1px solid var(--input-border);
  border-radius: 9px;
  font-family: var(--font-mono);
  font-weight: 600;
  cursor: pointer;
  transition: border-color var(--transition-fast), background-color var(--transition-fast);
}

.captcha-challenge:hover,
.captcha-challenge:focus-visible {
  background: var(--accent-soft);
  border-color: #9fc4af;
  outline: none;
}

.submit-item {
  margin-top: 6px;
  margin-bottom: 14px !important;
}

.login-button {
  width: 100%;
  min-height: 46px;
  border-radius: 9px !important;
}

.form-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  color: var(--text-muted);
  font-size: 12px;
}

.remember-row {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: var(--text-secondary);
  cursor: pointer;
}

.remember-row input {
  width: 15px;
  height: 15px;
  margin: 0;
  accent-color: var(--accent);
}

.helper-text {
  text-align: right;
}

.login-footer {
  display: flex;
  justify-content: space-between;
  margin-top: 46px;
  padding-top: 18px;
  color: #919a94;
  border-top: 1px solid var(--border-color);
  font-size: 11px;
}

.login-form :deep(input:-webkit-autofill),
.login-form :deep(input:-webkit-autofill:hover),
.login-form :deep(input:-webkit-autofill:focus),
.login-form :deep(input:-webkit-autofill:active) {
  -webkit-box-shadow: 0 0 0 1000px #ffffff inset !important;
  -webkit-text-fill-color: var(--text-primary) !important;
  caret-color: var(--text-primary);
}

@media (max-width: 1080px) {
  .login-shell {
    grid-template-columns: minmax(0, 1fr) minmax(400px, 0.9fr);
  }

  .visual-panel {
    padding: 32px;
    background-size: auto 58%;
  }

  .visual-copy h1 {
    font-size: 44px;
  }
}

@media (max-width: 820px) {
  .login-shell {
    display: block;
  }

  .visual-panel {
    display: none;
  }

  .login-panel {
    min-height: 100dvh;
    padding: 36px 24px;
  }

  .mobile-brand {
    display: flex;
  }
}

@media (max-width: 480px) {
  .login-panel {
    place-items: start center;
    padding-top: 26px;
  }

  .mobile-brand {
    margin-bottom: 34px;
  }

  .login-heading h2 {
    font-size: 30px;
  }

  .captcha-row {
    grid-template-columns: 1fr;
  }

  .form-meta {
    align-items: flex-start;
    flex-direction: column;
  }

  .helper-text {
    text-align: left;
  }
}
</style>
