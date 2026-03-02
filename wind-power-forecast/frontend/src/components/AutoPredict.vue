<!-- src/components/AutoPredict.vue -->
<template>
  <div 
    class="autopredict-container power-predict-container" 
    v-loading="loading" 
    element-loading-text="加载中，请稍候..."
    :class="{'animated-background': isAnimatedBackground.value, 'static-background': !isAnimatedBackground.value}"
  >
    <h1 class="page-title">自动化预测功能管理</h1>
    <div class="hero-section">
      <!-- Global buttons removed -->
      <el-row :gutter="24">
        <el-col :span="8" v-for="(item, index) in predictions" :key="index">
          <el-card class="prediction-card">
            <template #header>
              <span>{{ item.title }}</span>
            </template>
            <div class="button-group">
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
              
              <!-- 定时重启按钮已移除 -->
            </div>
            <div class="button-group extra">
              <el-button type="danger" @click="showConfirmDialog('deleteTask', '删除预测任务', `确定要从PM2中删除${item.title}吗？此操作不会删除脚本文件，但会移除任务记录。`, item.name)">删除</el-button>
              <!-- 详情按钮已移除 -->
              <el-button type="primary" @click="fetchLogs(item.name)">日志</el-button>
            </div>
          </el-card>
        </el-col>
      </el-row>
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
  </div>
</template>

<script setup>
import { ref, reactive, inject, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import axiosInstance from '../api/axios'
import farmService from '../utils/farmService'

const isAnimatedBackground = inject('isAnimatedBackground');

const predictions = reactive([
  {
    name: 'supershort',
    title: '超短期风电功率预测',
    status: false
  },
  {
    name: 'short',
    title: '短期风电功率预测',
    status: false
  },
  {
    name: 'medium',
    title: '中期风电功率预测',
    status: false
  }
])

const loading = ref(true)

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
const currentFarm = ref(farmService.getCurrentFarm())

const handleFarmChanged = (farmCode) => {
  currentFarm.value = farmCode
  fetchStatus()
}

onMounted(() => {
  farmService.addListener(handleFarmChanged)
  fetchStatus()
  intervalId = setInterval(fetchStatus, POLLING_INTERVAL)
})

onUnmounted(() => {
  farmService.removeListener(handleFarmChanged)
  if (intervalId) {
    clearInterval(intervalId)
    intervalId = null
  }
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
    if (errorDetails.data && errorDetails.data.error && errorDetails.data.error.includes('PM2')) {
      errorMessage = 'PM2服务错误'
    }
    ElMessage.error(errorMessage)
    console.error('详细错误:', errorDetails)
    return Promise.reject(error)
  }
)

const fetchStatus = async () => {
  loading.value = true
  try {
    const res = await apiClient.get('/api/status', {
      params: {
        farm_code: currentFarm.value
      }
    })
    predictions.forEach(p => {
      p.status = res.data[p.name] || false
    })
  } catch (error) {
    console.error('获取状态失败:', error)
  } finally {
    loading.value = false
  }
}

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
    // Removed cases for saveSettings, resurrectConfig, clearSavedConfig
    default:
      console.warn('未知操作:', confirmDialog.action)
  }
}

const handleControl = async (name, action) => {
  console.log('handleControl invoked', name, action)
  loading.value = true
  try {
    const res = await apiClient.post(`/api/${action}`, {
      type: name,
      farm_code: currentFarm.value
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

// 定时重启方法 (showScheduleDialog, setSchedule) 已移除
// 保存/加载/删除 PM2 配置方法 (saveSettings, resurrectConfig, clearSavedConfig) 已移除
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
      lines: 500,
      farm_code: currentFarm.value
    }
    if (logsFilters.logType === 'param') {
      // params.param_opt_day = getParamOptDay(currentPrediction) // getParamOptDay is removed
      // If param logs are specific to a day derived from task type, adjust or remove this logic
      // For now, removing it if getParamOptDay is fully removed
    }
    const res = await apiClient.get('/api/logs', { params })
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

// getTaskTitle might still be used by logs, so keeping it conditionally or removing if not used.

</script>

<style scoped>
/* Styles remain largely the same, but some related to removed dialogs might be implicitly unused */
.autopredict-container {
  min-height: 100vh;
  padding: 40px;
  position: relative;
  z-index: 1;
}

.power-predict-container {
  min-height: 100vh;
  background: linear-gradient(-45deg, #ee7752, #e73c7e, #23a6d5, #23d5ab);
  background-size: 400% 400%;
  animation: gradient 15s ease infinite;
  position: relative;
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

.page-title {
  color: white;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.hero-section {
  text-align: center;
  padding: 60px 20px;
  position: relative;
}

.hero-section::before {
  content: "✨";
  position: absolute;
  top: 0;
  left: 0;
  font-size: 24px;
  opacity: 0.7;
}

.hero-section::after {
  content: "✨";
  position: absolute;
  bottom: 0;
  right: 0;
  font-size: 24px;
  opacity: 0.7;
}

.autopredict-container h2 {
  font-size: 48px;
  font-weight: 600;
  margin-bottom: 40px;
  text-align: center;
  color: #1d1d1f;
  letter-spacing: -0.003em;
  line-height: 1.1;
}

.global-buttons {
  display: flex;
  gap: 16px;
  justify-content: center;
  margin-bottom: 24px;
}

.el-button {
  height: 40px;  
  padding: 0 20px;
  font-size: 15px;
  font-weight: 500;
  border-radius: 20px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  letter-spacing: -0.01em;
  border: none;
  min-width: 100px; 
}

.el-button--primary {
  background: #0071e3;
  color: #ffffff;
}

.el-button--primary:hover {
  background: #0077ed;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 113, 227, 0.12);
}

.el-button--success {
  background: #34c759;
  color: #ffffff;
}

.el-button--success:hover {
  background: #30b753;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(52, 199, 89, 0.12);
}

.el-button--danger {
  background: #ff3b30;
  color: #ffffff;
}

.el-button--danger:hover {
  background: #ff291e;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(255, 59, 48, 0.12);
}

.el-button--warning {
  background: #ff9500;
  color: #ffffff;
}

.el-button--warning:hover {
  background: #ff8500;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(255, 149, 0, 0.12);
}

.el-button--info {
  background: #8e8e93;
  color: #ffffff;
}

.el-button--info:hover {
  background: #7c7c82;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(142, 142, 147, 0.12);
}

.el-button.is-disabled,
.el-button.is-disabled:hover {
  background: #e5e5ea;
  color: #8e8e93;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.button-group {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  justify-content: center;
  align-items: center;
  padding: 12px 16px;
  margin-bottom: 0;
}

.button-group .el-button {
  width: 100%;
  justify-content: center;
  min-width: 80px;
}

.el-row {
  margin: 24px -16px;
}

.el-col {
  padding: 0 16px;
  margin-bottom: 24px;
}

.el-card {
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  border: 1px solid #f0f0f0;
  border-radius: 20px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
  padding: 16px;
}

.el-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
}

.prediction-card {
  padding: 30px;
  border: none;
}

.prediction-card :deep(.el-card__header) {
  padding: 0 0 20px 0;
  border-bottom: 1px solid #f2f2f2;
}

.prediction-card :deep(.el-card__header span) {
  font-size: 24px;
  font-weight: 500;
  color: #1d1d1f;
}

.el-dialog {
  border-radius: 20px;
  overflow: hidden;
  transform: none !important;
  margin: 0 auto !important;
  position: relative;
  max-width: 90%;
  top: 50%;
  margin-top: 0 !important;
}

:deep(.el-overlay-dialog) {
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: auto;
}

.el-dialog :deep(.el-dialog__header) {
  padding: 24px;
  margin: 0;
  background: #f5f5f7;
}

.el-dialog :deep(.el-dialog__title) {
  font-size: 20px;
  font-weight: 500;
  color: #1d1d1f;
}

.el-dialog :deep(.el-dialog__body) {
  padding: 24px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.el-dialog :deep(.el-dialog__body p) {
  margin: 0;
  text-align: center;
  width: 100%;
}

.el-dialog :deep(.el-dialog__footer) {
  padding: 16px 24px 24px;
  text-align: center;
}

.dialog-footer-buttons {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  width: 100%;
}

.dialog-footer-buttons .el-button {
  margin-left: 0;
  flex: 0 0 auto;
  min-width: 100px;
}

.info-content, .logs-content, .error-content, .history-detail-content {
  max-height: 600px;
  overflow-y: auto;
  background: #fafafa;
  padding: 24px;
  border-radius: 12px;
  font-family: "SF Mono", Monaco, Menlo, Consolas, monospace;
  font-size: 14px;
  line-height: 1.5;
  color: #1d1d1f;
}

.history-filters {
  margin-bottom: 24px;
}

.pagination-container {
  margin-top: 24px;
  display: flex;
  justify-content: center;
}

@media (max-width: 768px) {
  .autopredict-container {
    padding: 20px;
  }

  .autopredict-container h2 {
    font-size: 32px;
  }

  .el-button {
    height: 40px;
    padding: 0 20px;
    font-size: 14px;
  }

  .el-row {
    gap: 16px;  
    margin: 0 10px;  
  }
  
  .el-col {
    margin-bottom: 16px;  
  }
  
  .global-buttons {
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }
}

.logs-filters {
  margin-bottom: 20px;
  background: #f9f9f9;
  padding: 16px;
  border-radius: 8px;
}

/* Styles for removed dialogs and their contents can be cleaned up if desired */
/* .task-info-container, .task-status-cards, .script-info-section, .ultra-start-options, .task-date-selector might be unused now */

</style>
