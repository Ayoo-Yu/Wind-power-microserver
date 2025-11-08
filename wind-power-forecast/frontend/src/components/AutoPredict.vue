<!-- src/components/AutoPredict.vue -->
<template>
  <DigitalPage>
    <div
      class="autopredict"
      v-loading="loading"
      element-loading-text="加载中，请稍候..."
    >
      <header class="autopredict-hero digital-panel">
        <div class="hero-primary">
          <p class="hero-eyebrow">自动调度中心</p>
          <h1 class="hero-title">自动化预测功能管理</h1>
          <p class="hero-subtitle">集中管理超短期、短期、中期预测调度</p>
          <div class="hero-meta">
            <span class="digital-status-chip">
              当前场站：{{ selectedWindFarm || '未选择' }}
            </span>
            <div class="hero-metrics">
              <div class="hero-metric">
                <span class="hero-metric__label">运行中任务</span>
                <span class="hero-metric__value">{{ activePredictionCount }}</span>
              </div>
              <div class="hero-metric">
                <span class="hero-metric__label">待启用任务</span>
                <span class="hero-metric__value">{{ pendingPredictionCount }}</span>
              </div>
            </div>
          </div>
          <div class="hero-actions">
            <el-button type="primary" :loading="loading" @click="fetchStatus">
              刷新状态
            </el-button>
          </div>
        </div>
        <div class="hero-secondary">
          <h3 class="hero-secondary__title">调度概览</h3>
          <ul class="prediction-snapshot">
            <li
              v-for="snapshot in predictionSnapshots"
              :key="snapshot.name"
              class="prediction-snapshot__item"
            >
              <div class="snapshot-header">
                <span class="snapshot-title">{{ snapshot.title }}</span>
                <span
                  class="snapshot-status"
                  :class="snapshot.status ? 'is-online' : 'is-offline'"
                >
                  {{ snapshot.status ? '运行中' : '待启用' }}
                </span>
              </div>
              <p class="snapshot-meta">{{ snapshot.schedule }}</p>
              <p class="snapshot-meta">{{ snapshot.lastTriggered }}</p>
            </li>
          </ul>
        </div>
      </header>

      <section class="prediction-grid">
        <article
          v-for="(item, index) in predictions"
          :key="index"
          class="prediction-card digital-panel digital-panel--interactive"
        >
          <div class="prediction-card__header">
            <div class="prediction-card__title-group">
              <h3 class="prediction-card__title">{{ item.title }}</h3>
              <p class="prediction-card__subtitle">调度标识：{{ item.name }}</p>
            </div>
            <el-tag :type="item.status ? 'success' : 'info'" effect="dark">
              {{ item.status ? '已启用' : '未启用' }}
            </el-tag>
          </div>

          <div class="prediction-card__meta">
            <div class="meta-line">
              <span class="meta-label">最近触发</span>
              <span class="meta-value">
                {{ formatDateTime(item.meta.lastTriggeredAt) || '暂无记录' }}
              </span>
            </div>
            <div class="meta-line">
              <span class="meta-label">计划表达式</span>
              <span class="meta-value">
                {{ item.meta.scheduleCron || '默认计划' }}
              </span>
            </div>
          </div>

          <div class="prediction-card__actions">
            <div class="action-row">
              <el-button
                :type="item.status ? 'success' : 'primary'"
                @click="showConfirmDialog('startTask', '启用预测任务', `确定要启用${item.title}吗？`, item.name)"
                :disabled="item.status"
              >
                {{ item.status ? '运行中' : '启用' }}
              </el-button>

              <el-button
                type="danger"
                @click="showConfirmDialog('stopTask', '停止预测任务', `确定要停止${item.title}吗？此操作会中断当前预测。`, item.name)"
                :disabled="!item.status"
              >
                停止
              </el-button>
            </div>
            <div class="action-row">
              <el-button
                type="warning"
                @click="showConfirmDialog('triggerTask', '手动触发', `立即触发一次${item.title}的训练和预测任务？`, item.name)"
                :disabled="!item.status"
              >
                手动触发
              </el-button>
              <el-button
                type="danger"
                @click="showConfirmDialog('deleteTask', '删除预测任务', `确定要删除${item.title}的调度配置吗？`, item.name)"
              >
                删除
              </el-button>
              <el-button type="primary" @click="fetchLogs(item.name)">
                日志
              </el-button>
            </div>
          </div>
        </article>
      </section>
    </div>

    <!-- 操作确认对话框 -->
    <el-dialog 
      :title="confirmDialog.title" 
      v-model="confirmDialog.visible" 
      width="30%"
    >
      <p>{{ confirmDialog.message }}</p>
      <template #footer>
        <div class="dialog-footer-buttons">
          <el-button type="primary" @click="executeConfirmedAction">确定</el-button>
          <el-button @click="confirmDialog.visible = false">取消</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 定时重启设置对话框已移除 -->
    <!-- 脚本详情对话框已移除 -->

    <!-- 脚本日志对话框 -->
    <el-dialog 
      title="脚本日志" 
      v-model="logsDialogVisible" 
      width="80%"
    >
      <div class="logs-filters">
        <el-form :inline="true">
          <el-form-item label="日志类型">
            <el-select v-model="logsFilters.logType" placeholder="选择日志类型" @change="handleLogTypeChange" style="min-width: 180px;">
              <el-option v-for="option in getLogTypeOptions()" :key="option.value" :label="option.label" :value="option.value"></el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="日期">
            <el-date-picker
              v-model="logsFilters.date"
              type="date"
              placeholder="选择日期"
              format="YYYY-MM-DD"
              value-format="YYYYMMDD"
              style="min-width: 180px;"
            ></el-date-picker>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="fetchLogsByFilter">查询</el-button>
            <el-button @click="resetLogsFilters">重置</el-button>
          </el-form-item>
        </el-form>
      </div>
      <pre class="logs-content">{{ logsContent }}</pre>
      <template #footer>
        <div class="dialog-footer-buttons">
          <el-button type="primary" @click="fetchLogsByFilter">刷新</el-button>
          <el-button @click="logsDialogVisible = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 错误详情对话框 -->
    <el-dialog 
      :title="errorTitle"
      v-model="errorDialogVisible" 
      width="50%"
    >
      <pre class="error-content">{{ errorDetails }}</pre>
      <template #footer>
        <div class="dialog-footer-buttons">
          <el-button @click="errorDialogVisible = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 任务历史记录对话框已移除 -->
    <!-- 历史记录详情对话框已移除 -->
  </DigitalPage>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import axiosInstance from '../api/axios'
import { useWindFarmStore } from '../store/windFarm'
import DigitalPage from './common/DigitalPage.vue'

const predictions = reactive([
  {
    name: 'supershort',
    title: '超短期风电功率预测',
    status: false,
    meta: {
      lastTriggeredAt: null,
      scheduleCron: null,
    },
  },
  {
    name: 'short',
    title: '短期风电功率预测',
    status: false,
    meta: {
      lastTriggeredAt: null,
      scheduleCron: null,
    },
  },
  {
    name: 'medium',
    title: '中期风电功率预测',
    status: false,
    meta: {
      lastTriggeredAt: null,
      scheduleCron: null,
    },
  },
])

const loading = ref(true)
const { selectedWindFarm } = useWindFarmStore()

// 定时重启相关变量 - 已移除
// const scheduleDialogVisible = ref(false)
// const scheduleTime = ref('')
let currentPrediction = '' // Still needed for logs and other actions

// 脚本详情与日志相关变量
// const scriptInfoDialogVisible = ref(false) // Removed
// const scriptInfo = ref('') // Removed
const logsDialogVisible = ref(false)
const logsContent = ref('')
const logsFilters = reactive({
  logType: '',
  date: ''
})

const errorDialogVisible = ref(false)
const errorDetails = ref('')
const errorTitle = ref('操作失败')

const confirmDialog = reactive({
  visible: false,
  title: '',
  message: '',
  action: '',
  params: null
})

// 任务历史记录相关变量 - 已移除
// const historyDialogVisible = ref(false)
// const historyRecords = ref([])
// const historyFilters = reactive({
//   taskType: '',
//   action: ''
// })
// const historyPagination = reactive({
//   currentPage: 1,
//   pageSize: 20,
//   total: 0
// })
// const historyDetailDialogVisible = ref(false)
// const historyDetailContent = ref('')

// 详情相关变量 - 移除与详情弹窗相关的部分
// const taskStatus = reactive({
//   training: false,
//   prediction: false,
//   paramOpt: false,
//   trainingTime: '',
//   predictionTime: '',
//   paramOptTime: '',
//   predictionCount: 0,
//   predictionCompleted: false
// })

// const taskDateInfo = reactive({
//   selectedDate: new Date().toISOString().slice(0, 10).replace(/-/g, ''),
//   displayDate: '今天'
// })

const POLLING_INTERVAL = 60000
let intervalId = null

onMounted(() => {
  fetchStatus()
  intervalId = setInterval(fetchStatus, POLLING_INTERVAL)
})

onUnmounted(() => {
  if (intervalId) {
    clearInterval(intervalId)
    intervalId = null
  }
})

watch(selectedWindFarm, () => {
  fetchStatus()
})

const showErrorDialog = (title, details) => {
  errorTitle.value = title || '操作失败'
  errorDetails.value = typeof details === 'object' ? JSON.stringify(details, null, 2) : String(details)
  errorDialogVisible.value = true
}

const apiClient = axiosInstance;

apiClient.interceptors.response.use(
  response => {
    if (response.data && response.data.warning) {
      ElMessage.warning(response.data.warning)
    }
    return response
  },
  error => {
    console.error('API请求出错:', error)
    let errorMessage = '请求失败'
    let errorDetails = {}
    if (error.response) {
      errorMessage = `服务器返回错误 (${error.response.status})`
      errorDetails = {
        status: error.response.status,
        statusText: error.response.statusText,
        data: error.response.data
      }
    } else if (error.request) {
      errorMessage = '服务器无响应'
      errorDetails = {
        message: '请求已发送，但未收到服务器响应',
        request: error.request
      }
    } else {
      errorMessage = '请求配置错误'
      errorDetails = {
        message: error.message
      }
    }
    ElMessage.error(errorMessage)
    console.error('详细错误:', errorDetails)
    return Promise.reject(error)
  }
)

const formatDateTime = value => {
  if (!value) {
    return '无记录'
  }
  try {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) {
      return value
    }
    return date.toLocaleString()
  } catch (error) {
    return value
  }
}

const fetchStatus = async () => {
  loading.value = true
  try {
    const res = await apiClient.get('status', {
      params: {
        wind_farm_code: selectedWindFarm.value,
      },
    })
    const meta = res.data.meta || {}
    predictions.forEach(p => {
      p.status = Boolean(meta[p.name]?.enabled ?? res.data[p.name])
      p.meta.lastTriggeredAt = meta[p.name]?.last_triggered_at || meta[p.name]?.lastTriggeredAt || null
      p.meta.scheduleCron = meta[p.name]?.schedule_cron || meta[p.name]?.scheduleCron || null
    })
  } catch (error) {
    console.error('获取状态失败:', error)
  } finally {
    loading.value = false
  }
}

const predictionSnapshots = computed(() =>
  predictions.map(item => ({
    name: item.name,
    title: item.title,
    status: item.status,
    schedule: item.meta.scheduleCron ? `计划：${item.meta.scheduleCron}` : '计划：未配置',
    lastTriggered: `最近触发：${formatDateTime(item.meta.lastTriggeredAt)}`
  }))
)

const activePredictionCount = computed(() =>
  predictions.filter(item => item.status).length
)

const pendingPredictionCount = computed(() =>
  predictions.length - activePredictionCount.value
)

const showConfirmDialog = (action, title, message, params = null) => {
  confirmDialog.action = action
  confirmDialog.title = title
  confirmDialog.message = message
  confirmDialog.params = params
  confirmDialog.visible = true
}

const executeConfirmedAction = () => {
  confirmDialog.visible = false
  switch (confirmDialog.action) {
    case 'startTask':
      handleControl(confirmDialog.params, 'start')
      break
    case 'stopTask':
      handleControl(confirmDialog.params, 'stop')
      break
    case 'deleteTask':
      handleControl(confirmDialog.params, 'delete')
      break
    case 'triggerTask':
      handleTrigger(confirmDialog.params)
      break
    // Removed cases for saveSettings, resurrectConfig, clearSavedConfig
    default:
      console.warn('未知操作:', confirmDialog.action)
  }
}

const handleControl = async (name, action) => {
  console.log('handleControl invoked', name, action)
  loading.value = true
  try {
    const res = await apiClient.post(`${action}`, {
      type: name,
      wind_farm_code: selectedWindFarm.value,
    })
    if (res.data.warning) {
      ElMessage.warning(res.data.warning)
    } else {
      ElMessage.success(res.data.message || '操作成功')
    }
    setTimeout(async () => {
      await fetchStatus()
    }, 1000)
  } catch (error) {
    if (error.response && error.response.data) {
      const errorData = error.response.data
      showErrorDialog(
        `${action} ${name} 失败`, 
        errorData.details || errorData.error || error.message
      )
    }
  } finally {
    loading.value = false
  }
}

const handleTrigger = async (name) => {
  loading.value = true
  try {
    const res = await apiClient.post('trigger', {
      type: name,
      wind_farm_code: selectedWindFarm.value,
    })
    ElMessage.success(res.data.message || '任务已触发')
    await fetchStatus()
  } catch (error) {
    if (error.response && error.response.data) {
      const errorData = error.response.data
      showErrorDialog(
        `触发 ${name} 失败`,
        errorData.details || errorData.error || error.message
      )
    }
  } finally {
    loading.value = false
  }
}

// 定时重启方法 (showScheduleDialog, setSchedule) 已移除
// 保存/加载/删除 调度配置的方法 (saveSettings, resurrectConfig, clearSavedConfig) 已移除
// 查询脚本详情方法 (fetchScriptInfo) 已移除
// 获取任务状态方法 (fetchTaskStatus, refreshTaskStatus, fetchTaskStatusByDate, resetTaskDateInfo) 已移除
// 获取任务标题方法 (getTaskTitle) 已移除 (如果日志部分不需要可以彻底删除)

// 获取脚本日志
const fetchLogs = async (name) => {
  currentPrediction = name // Set currentPrediction for logs
  logsDialogVisible.value = true
  logsFilters.logType = 'train'
  logsFilters.date = new Date().toISOString().slice(0, 10).replace(/-/g, '')
  fetchLogsByFilter()
}

const fetchLogsByFilter = async () => {
  loading.value = true
  try {
    const params = {
      type: currentPrediction,
      logType: logsFilters.logType || 'train',
      date: logsFilters.date || new Date().toISOString().slice(0, 10).replace(/-/g, ''),
      lines: 500
    }
    if (logsFilters.logType === 'param') {
      // params.param_opt_day = getParamOptDay(currentPrediction) // getParamOptDay is removed
      // If param logs are specific to a day derived from task type, adjust or remove this logic
      // For now, removing it if getParamOptDay is fully removed
    }
    const res = await apiClient.get('logs', {
      params: {
        ...params,
        wind_farm_code: selectedWindFarm.value,
      },
    })
    logsContent.value = res.data.logs || '暂无日志信息'
  } catch (error) {
    console.error('获取日志失败:', error)
    if (error.response && error.response.data) {
      showErrorDialog(
        '获取日志失败', 
        error.response.data.details || error.response.data.error || error.message
      )
    }
  } finally {
    loading.value = false
  }
}

const resetLogsFilters = () => {
  logsFilters.logType = 'train'
  logsFilters.date = new Date().toISOString().slice(0, 10).replace(/-/g, '')
  fetchLogsByFilter()
}

const getLogTypeOptions = () => {
  if (currentPrediction === 'supershort') {
    return [
      // { label: '主调度日志', value: 'main' },
      { label: '每日训练日志', value: 'train' },
      { label: '实时预测日志', value: 'predict' }
    ]
  } 
  return [
    { label: '训练日志', value: 'train' },
    // { label: '参数优化日志', value: 'param' } // Consider if 'param' logs still relevant/obtainable without 'details'
  ]
}

const handleLogTypeChange = () => {
  fetchLogsByFilter()
}

// 任务历史记录相关方法 (openHistoryDialog, fetchTaskHistory, resetHistoryFilters, handleSizeChange, handleCurrentChange, showHistoryDetail) 已移除
// 历史记录辅助方法 (getTaskTypeTagType, getTaskTypeLabel, getActionTagType, getActionLabel, getStatusTagType, getStatusLabel) 已移除
// 参数优化星期相关方法 (getParamOptWeekday, getParamOptDay) 已移除
// 预测任务状态文本/类型方法 (getTaskPredictionType, getTaskPredictionStatus) 已移除

</script>

<style scoped>
.autopredict {
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.autopredict-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
  gap: 28px;
  align-items: stretch;
}

.hero-primary {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.hero-eyebrow {
  margin: 0;
  font-size: 12px;
  letter-spacing: 0.4em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.hero-title {
  margin: 0;
  font-size: 40px;
  font-weight: 600;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--text-primary);
}

.hero-subtitle {
  margin: 0;
  font-size: 16px;
  letter-spacing: 0.08em;
  color: var(--text-secondary);
  line-height: 1.7;
}

.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: center;
}

.hero-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.hero-metric {
  min-width: 140px;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid rgba(66, 195, 255, 0.25);
  background: linear-gradient(150deg, rgba(9, 24, 48, 0.65) 0%, rgba(6, 18, 36, 0.72) 100%);
  box-shadow: 0 18px 48px rgba(4, 18, 36, 0.35);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.hero-metric__label {
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.hero-metric__value {
  font-family: 'Rajdhani', 'Inter', sans-serif;
  font-size: 32px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent-primary, #38c4ff);
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.hero-secondary {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.hero-secondary__title {
  margin: 0;
  font-size: 18px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.prediction-snapshot {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 16px;
}

.prediction-snapshot__item {
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid rgba(66, 195, 255, 0.2);
  background: linear-gradient(145deg, rgba(9, 24, 48, 0.9) 0%, rgba(5, 18, 36, 0.82) 100%);
  box-shadow: 0 20px 48px rgba(2, 16, 42, 0.45);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.snapshot-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.snapshot-title {
  font-size: 16px;
  letter-spacing: 0.08em;
  color: var(--text-primary);
}

.snapshot-status {
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  border: 1px solid rgba(66, 195, 255, 0.32);
  background: rgba(66, 195, 255, 0.12);
}

.snapshot-status.is-online {
  border-color: rgba(34, 246, 170, 0.55);
  background: rgba(34, 246, 170, 0.18);
  color: #22f6aa;
}

.snapshot-status.is-offline {
  border-color: rgba(215, 87, 255, 0.45);
  background: rgba(215, 87, 255, 0.16);
  color: #f4a4ff;
}

.snapshot-meta {
  margin: 0;
  font-size: 13px;
  letter-spacing: 0.06em;
  color: var(--text-secondary);
}

.prediction-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 24px;
}

.prediction-card {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-height: 100%;
}

.prediction-card__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.prediction-card__title-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.prediction-card__title {
  margin: 0;
  font-size: 20px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-primary);
}

.prediction-card__subtitle {
  margin: 0;
  font-size: 13px;
  letter-spacing: 0.08em;
  color: var(--text-secondary);
}

.prediction-card__meta {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.meta-line {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
  color: var(--text-secondary);
}

.meta-label {
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.meta-value {
  color: var(--text-primary);
  letter-spacing: 0.08em;
}

.prediction-card__actions {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.dialog-footer-buttons {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

@media (max-width: 1280px) {
  .autopredict-hero {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .prediction-grid {
    grid-template-columns: 1fr;
  }

  .hero-title {
    font-size: 32px;
  }

  .hero-metric__value {
    font-size: 26px;
  }
}
</style>