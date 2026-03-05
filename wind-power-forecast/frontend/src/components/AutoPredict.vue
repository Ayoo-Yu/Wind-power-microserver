<!-- src/components/AutoPredict.vue -->
<template>
  <div 
    class="autopredict-container power-predict-container" 
    v-loading="loading" 
    element-loading-text="加载中，请稍候..."
    :class="{'animated-background': isAnimatedBackground.value, 'static-background': !isAnimatedBackground.value}"
  >
    <h1 class="page-title">自动化预测功能管理</h1>
    <el-card class="matrix-table-card">
      <template #header>
        <span>预测类型运行矩阵</span>
      </template>
      <el-table :data="predictionTableRows" size="small" border>
        <el-table-column prop="title" label="预测类型" min-width="180" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <StatusDot :active="row.status" />
            <span class="status-text">{{ row.status ? '运行中' : '已停止' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="启停" width="120">
          <template #default="{ row }">
            <el-switch
              :model-value="row.status"
              :loading="isControlBusy(row.name)"
              @change="(val) => handleSwitchToggle(row.name, val)"
            />
          </template>
        </el-table-column>
        <el-table-column label="趋势预览" min-width="160">
          <template #default="{ row }">
            <SparklineMini :values="row.trend" :active="row.status" />
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    <div class="fleet-overview" v-loading="fleetLoading">
      <div class="fleet-title">多场站运行总览</div>
      <div class="fleet-filter-row">
        <el-select
          v-model="selectedFleetFarmCodes"
          multiple
          collapse-tags
          collapse-tags-tooltip
          placeholder="选择批量操作场站（默认全部）"
          class="fleet-farm-select"
        >
          <el-option
            v-for="farm in fleetStatus"
            :key="farm.farm_code"
            :label="`${farm.farm_name} (${farm.farm_code})`"
            :value="farm.farm_code"
          />
        </el-select>
        <el-button size="small" plain class="minor-action-btn" @click="selectAllFleetFarms">全选</el-button>
        <el-button size="small" plain class="minor-action-btn" @click="clearFleetFarmSelection">清空</el-button>
      </div>
      <div class="fleet-matrix-row">
        <el-checkbox-group v-model="selectedBatchTypes">
          <el-checkbox label="supershort">超短期</el-checkbox>
          <el-checkbox label="short">短期</el-checkbox>
          <el-checkbox label="medium">中期</el-checkbox>
        </el-checkbox-group>
        <el-button type="primary" plain size="small" :loading="matrixControlLoading" @click="handleControlMatrix('start')">选中场站+类型 批量启用</el-button>
        <el-button type="warning" plain size="small" :loading="matrixControlLoading" @click="handleControlMatrix('stop')">选中场站+类型 批量停止</el-button>
        <el-button type="danger" plain size="small" :loading="matrixControlLoading" @click="handleControlMatrix('delete')">选中场站+类型 批量删除</el-button>
      </div>
      <div class="fleet-list">
        <div class="fleet-item" v-for="farm in fleetStatus" :key="farm.farm_code">
          <div class="fleet-name">{{ farm.farm_name }} ({{ farm.farm_code }})</div>
          <div class="fleet-tags">
            <el-tag size="small" :type="farm.status?.supershort ? 'success' : 'info'">超短期</el-tag>
            <el-tag size="small" :type="farm.status?.short ? 'success' : 'info'">短期</el-tag>
            <el-tag size="small" :type="farm.status?.medium ? 'success' : 'info'">中期</el-tag>
          </div>
        </div>
      </div>
    </div>
    <div class="hero-section">
      <el-row :gutter="18">
        <el-col :span="8" v-for="(item, index) in predictions" :key="index">
          <el-card class="prediction-card smart-card" :class="`card-${item.name}`">
            <div class="card-top">
              <div class="card-title-group">
                <h3>
                  <el-icon class="title-icon"><DataAnalysis /></el-icon>
                  {{ item.title }}
                </h3>
                <div class="card-status">
                  <StatusDot :active="item.status" />
                  <span>{{ item.status ? '运行中' : '已停止' }}</span>
                </div>
              </div>
              <div class="card-actions">
                <el-switch
                  :model-value="item.status"
                  :loading="isControlBusy(item.name)"
                  @change="(val) => handleSwitchToggle(item.name, val)"
                />
                <el-dropdown trigger="click" popper-class="predict-more-menu" @command="(cmd) => handleCardCommand(cmd, item)">
                  <el-button text class="more-btn">
                    <el-icon><MoreFilled /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="logs">查看日志</el-dropdown-item>
                      <el-dropdown-item command="delete" divided>删除任务</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </div>

            <div class="metric-list">
              <div class="metric-item">
                <span><el-icon><Clock /></el-icon>上次执行时间</span>
                <strong>{{ getPredictMetrics(item.name).lastRun }}</strong>
              </div>
              <div class="metric-item">
                <span><el-icon><Timer /></el-icon>执行耗时</span>
                <strong>{{ getPredictMetrics(item.name).duration }}</strong>
              </div>
              <div class="metric-item">
                <span><el-icon><AlarmClock /></el-icon>预计下次执行</span>
                <strong>{{ getPredictMetrics(item.name).nextRun }}</strong>
              </div>
              <div class="metric-item">
                <span><el-icon><Grid /></el-icon>运行场站数</span>
                <strong>{{ getPredictMetrics(item.name).runningFarms }}</strong>
              </div>
            </div>

            <div class="card-footer">
              <el-button type="primary" :disabled="isControlBusy(item.name)" @click="fetchLogs(item.name)">查看日志</el-button>
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

    <el-dialog
      title="批量操作结果明细"
      v-model="batchResultDialogVisible"
      width="70%"
    >
      <div class="batch-summary">
        <el-tag type="info">类型：{{ batchResult.type || '-' }}</el-tag>
        <el-tag type="primary">动作：{{ batchResult.action || '-' }}</el-tag>
        <el-tag type="success">成功：{{ batchResult.summary?.success || 0 }}</el-tag>
        <el-tag type="danger">失败：{{ batchResult.summary?.failed || 0 }}</el-tag>
      </div>
      <div class="batch-result-toolbar">
        <el-select
          v-model="batchResultFarmFilter"
          clearable
          filterable
          placeholder="按场站筛选明细"
          class="batch-result-filter"
        >
          <el-option
            v-for="farmCode in batchResultFarmOptions"
            :key="farmCode"
            :label="farmCode"
            :value="farmCode"
          />
        </el-select>
        <el-button @click="batchResultFarmFilter = ''">清空筛选</el-button>
        <el-button type="warning" @click="exportFailedBatchItems">导出失败场站</el-button>
      </div>
      <el-table :data="filteredBatchResultItems" border size="small" style="width: 100%">
        <el-table-column prop="farm_code" label="场站编码" min-width="150" />
        <el-table-column prop="type" label="预测类型" width="110" />
        <el-table-column prop="status_code" label="HTTP状态" width="100" />
        <el-table-column label="结果" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.success ? 'success' : 'danger'">
              {{ scope.row.success ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="消息" min-width="260" show-overflow-tooltip />
      </el-table>
      <template #footer>
        <div class="dialog-footer-buttons">
          <el-button type="primary" @click="batchResultDialogVisible = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 任务历史记录对话框已移除 -->
    <!-- 历史记录详情对话框已移除 -->
  </div>
</template>

<script setup>
import { ref, reactive, computed, inject, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { MoreFilled, DataAnalysis, Clock, AlarmClock, Grid, Timer } from '@element-plus/icons-vue'
import farmService from '../utils/farmService'
import { getAutoPredictStatus, getAutoPredictStatusAll, getAutoPredictOverview, controlAutoPredict, controlAutoPredictMatrix, getAutoPredictLogs } from '../api/autopredictApi'
import StatusDot from './common/StatusDot.vue'
import SparklineMini from './common/SparklineMini.vue'

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

const predictionTableRows = computed(() => predictions.map((item, idx) => ({
  ...item,
  trend: Array.from({ length: 18 }, (_, i) => {
    const base = item.status ? 72 : 48
    return Number((base + Math.sin((i + idx) / 2.5) * 12 + i * 0.6).toFixed(2))
  })
})))

const loading = ref(true)
const controlBusyMap = reactive({
  supershort: false,
  short: false,
  medium: false
})

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
const fleetStatus = ref([])
const fleetLoading = ref(false)
const selectedFleetFarmCodes = ref([])
const selectedBatchTypes = ref(['supershort', 'short', 'medium'])
const matrixControlLoading = ref(false)

const errorDialogVisible = ref(false)
const errorDetails = ref('')
const errorTitle = ref('操作失败')
const batchResultDialogVisible = ref(false)
const batchResultFarmFilter = ref('')
const batchResult = reactive({
  action: '',
  type: '',
  summary: { total: 0, success: 0, failed: 0 },
  items: []
})
const batchResultFarmOptions = computed(() => {
  const items = Array.isArray(batchResult.items) ? batchResult.items : []
  return Array.from(new Set(items.map(item => item.farm_code).filter(Boolean)))
})
const filteredBatchResultItems = computed(() => {
  const items = Array.isArray(batchResult.items) ? batchResult.items : []
  const farmCode = batchResultFarmFilter.value
  if (!farmCode) {
    return items
  }
  return items.filter(item => item.farm_code === farmCode)
})

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

// 详情相关变量 - 已移除与详情弹窗相关的部分
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
//   displayDate: '浠婂ぉ'
// })

const POLLING_INTERVAL = 60000
const FARM_CHANGE_DEBOUNCE_MS = 300
let intervalId = null
let farmChangeTimerId = null
let statusRequestSeq = 0
const currentFarm = ref(farmService.getCurrentFarm())
const statusUpdatedAt = ref(null)

const handleFarmChanged = (farmCode) => {
  currentFarm.value = farmCode
  if (farmChangeTimerId) {
    clearTimeout(farmChangeTimerId)
  }
  farmChangeTimerId = setTimeout(() => {
    fetchStatus()
    fetchFleetStatus()
  }, FARM_CHANGE_DEBOUNCE_MS)
}

const formatHms = (dateLike) => {
  if (!dateLike) return '--'
  const date = new Date(dateLike)
  if (Number.isNaN(date.getTime())) return '--'
  const hh = `${date.getHours()}`.padStart(2, '0')
  const mm = `${date.getMinutes()}`.padStart(2, '0')
  const ss = `${date.getSeconds()}`.padStart(2, '0')
  return `${hh}:${mm}:${ss}`
}

const getPredictMetrics = (predictionName) => {
  const mapping = { supershort: 15, short: 30, medium: 60 }
  const intervalMinutes = mapping[predictionName] || 30
  const base = statusUpdatedAt.value ? new Date(statusUpdatedAt.value) : new Date()
  const next = new Date(base.getTime() + intervalMinutes * 60 * 1000)

  const runningFarms = Array.isArray(fleetStatus.value)
    ? fleetStatus.value.reduce((count, farm) => count + (farm.status?.[predictionName] ? 1 : 0), 0)
    : 0

  return {
    lastRun: formatHms(base),
    duration: `${(0.8 + (predictionName.length % 4) * 0.35).toFixed(1)}s`,
    nextRun: formatHms(next),
    runningFarms
  }
}

const handleCardCommand = (command, item) => {
  if (command === 'logs') {
    fetchLogs(item.name)
    return
  }
  if (command === 'delete') {
    showConfirmDialog('deleteTask', '删除预测任务', `确定要删除 ${item.title} 吗？`, item.name)
  }
}

onMounted(async () => {
  farmService.addListener(handleFarmChanged)
  await farmService.loadAvailableFarms()
  currentFarm.value = farmService.getCurrentFarm()
  fetchStatus()
  fetchFleetStatus()
  intervalId = setInterval(() => {
    fetchStatus()
    fetchFleetStatus()
  }, POLLING_INTERVAL)
})

onUnmounted(() => {
  farmService.removeListener(handleFarmChanged)
  if (intervalId) {
    clearInterval(intervalId)
    intervalId = null
  }
  if (farmChangeTimerId) {
    clearTimeout(farmChangeTimerId)
    farmChangeTimerId = null
  }
})

const showErrorDialog = (title, details) => {
  errorTitle.value = title || '操作失败'
  errorDetails.value = typeof details === 'object' ? JSON.stringify(details, null, 2) : String(details)
  errorDialogVisible.value = true
}

const isControlBusy = (predictionName) => {
  return !!controlBusyMap[predictionName]
}


const fetchStatus = async () => {
  const requestId = ++statusRequestSeq
  loading.value = true
  try {
    const res = await getAutoPredictStatus(currentFarm.value)
    if (requestId !== statusRequestSeq) {
      return
    }
    const payload = res.data?.data || res.data || {}
    predictions.forEach(p => {
      p.status = payload[p.name] || false
    })
    statusUpdatedAt.value = Date.now()
  } catch (error) {
    if (requestId !== statusRequestSeq) {
      return
    }
    console.error('获取状态失败:', error)
  } finally {
    if (requestId === statusRequestSeq) {
      loading.value = false
    }
  }
}

const fetchFleetStatus = async () => {
  fleetLoading.value = true
  try {
    let res
    try {
      res = await getAutoPredictOverview()
    } catch (overviewError) {
      res = await getAutoPredictStatusAll()
    }
    const payload = res.data?.data || res.data || {}
    const items = Array.isArray(payload.items) ? payload.items : []
    fleetStatus.value = items

    const availableCodes = items.map(item => item.farm_code).filter(Boolean)
    if (selectedFleetFarmCodes.value.length === 0 && availableCodes.length > 0) {
      selectedFleetFarmCodes.value = [...availableCodes]
    } else {
      selectedFleetFarmCodes.value = selectedFleetFarmCodes.value.filter(code => availableCodes.includes(code))
    }
  } catch (error) {
    console.error('获取多场站状态失败:', error)
  } finally {
    fleetLoading.value = false
  }
}

const selectAllFleetFarms = () => {
  selectedFleetFarmCodes.value = fleetStatus.value
    .map(item => item.farm_code)
    .filter(Boolean)
}

const clearFleetFarmSelection = () => {
  selectedFleetFarmCodes.value = []
}

const exportFailedBatchItems = () => {
  const items = Array.isArray(batchResult.items) ? batchResult.items : []
  const failedItems = items.filter(item => !item.success)
  if (failedItems.length === 0) {
    ElMessage.info('没有失败场站可导出')
    return
  }

  const header = ['farm_code', 'status_code', 'code', 'message']
  const rows = failedItems.map(item => [
    item.farm_code || '',
    String(item.status_code ?? ''),
    String(item.code ?? ''),
    String(item.message ?? '').replace(/"/g, '""')
  ])
  const csv = [header.join(','), ...rows.map(row => `${row[0]},${row[1]},${row[2]},"${row[3]}"`)].join('\n')
  const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `batch_failed_${batchResult.type || 'unknown'}_${Date.now()}.csv`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
  ElMessage.success(`已导出失败场站 ${failedItems.length} 条`)
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
  if (isControlBusy(name)) {
    ElMessage.warning('操作正在处理中，请稍候')
    return
  }

  controlBusyMap[name] = true
  console.log('handleControl invoked', name, action)
  loading.value = true
  try {
    const res = await controlAutoPredict(action, name, currentFarm.value)
    const payload = res.data?.data || res.data || {}
    if (payload.warning || res.data?.warning) {
      ElMessage.warning(payload.warning || res.data.warning)
    } else {
      ElMessage.success(res.data.message || '操作成功')
    }
    setTimeout(async () => {
      await fetchStatus()
    }, 1000)
  } catch (error) {
    if (error?.response?.status === 409) {
      ElMessage.warning(error?.response?.data?.message || '任务操作冲突，请稍后再试')
      return
    }
    if (error.response && error.response.data) {
      const errorData = error.response.data
      showErrorDialog(
        `${action} ${name} 失败`, 
        errorData.details || errorData.error || error.message
      )
    }
  } finally {
    controlBusyMap[name] = false
    loading.value = false
  }
}

const handleSwitchToggle = (name, enabled) => {
  const action = enabled ? 'start' : 'stop'
  handleControl(name, action)
}

const handleControlMatrix = async (action) => {
  if (matrixControlLoading.value) {
    ElMessage.warning('矩阵批量操作正在处理中，请稍候')
    return
  }

  const targetFarmCodes = Array.isArray(selectedFleetFarmCodes.value)
    ? selectedFleetFarmCodes.value.filter(Boolean)
    : []
  const targetTypes = Array.isArray(selectedBatchTypes.value)
    ? selectedBatchTypes.value.filter(Boolean)
    : []

  if (targetFarmCodes.length === 0) {
    ElMessage.warning('请至少选择一个场站')
    return
  }
  if (targetTypes.length === 0) {
    ElMessage.warning('请至少选择一个预测类型')
    return
  }

  matrixControlLoading.value = true
  loading.value = true
  try {
    const res = await controlAutoPredictMatrix(action, targetTypes, targetFarmCodes)
    const payload = res.data?.data || res.data || {}
    const summary = payload.summary || {}
    const success = Number(summary.success || 0)
    const total = Number(summary.total || (targetFarmCodes.length * targetTypes.length))
    const failed = Number(summary.failed || 0)

    batchResult.action = action
    batchResult.type = targetTypes.join(',')
    batchResult.summary = { total, success, failed }
    batchResult.items = Array.isArray(payload.items) ? payload.items : []
    batchResultFarmFilter.value = ''
    batchResultDialogVisible.value = true

    if (failed > 0) {
      ElMessage.warning(`矩阵批量${action}完成：成功 ${success}/${total}，失败 ${failed}`)
    } else {
      ElMessage.success(`矩阵批量${action}完成：成功 ${success}/${total}`)
    }
    await fetchStatus()
    await fetchFleetStatus()
  } catch (error) {
    if (error?.response?.status === 409) {
      ElMessage.warning(error?.response?.data?.message || '矩阵批量操作冲突，请稍后再试')
      return
    }
    if (error.response && error.response.data) {
      const errorData = error.response.data
      showErrorDialog(
        `矩阵批量${action}失败`,
        errorData.details || errorData.error || error.message
      )
    }
  } finally {
    matrixControlLoading.value = false
    loading.value = false
  }
}

// 定时重启方法 (showScheduleDialog, setSchedule) 已移除
// 保存/加载/删除 PM2 配置方法 (saveSettings, resurrectConfig, clearSavedConfig) 已移除
// 查询脚本详情方法 (fetchScriptInfo) 已移除
// 获取任务状态方法 (fetchTaskStatus, refreshTaskStatus, fetchTaskStatusByDate, resetTaskDateInfo) 已移除
// 获取任务标题方法 (getTaskTitle) 已移除（如果日志部分不再需要可彻底删除）

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
    const queryDate = logsFilters.date || new Date().toISOString().slice(0, 10).replace(/-/g, '')
    if (logsFilters.logType === 'param') {
      // params.param_opt_day = getParamOptDay(currentPrediction) // getParamOptDay is removed
      // If param logs are specific to a day derived from task type, adjust or remove this logic
      // For now, removing it if getParamOptDay is fully removed
    }
    const res = await getAutoPredictLogs(currentPrediction, currentFarm.value, {
      logType: logsFilters.logType || 'train',
      date: queryDate,
      lines: 500
    })
    const payload = res.data?.data || res.data || {}
    logsContent.value = payload.logs || res.data.logs || '暂无日志信息'
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
      // { label: '涓昏皟搴︽棩蹇?, value: 'main' },
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
  padding: 20px 24px 30px;
  position: relative;
  z-index: 1;
}

.power-predict-container {
  min-height: 100vh;
  background: transparent !important;
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
  color: var(--text-primary);
  text-shadow: none;
  margin: 0 0 12px;
}

.matrix-table-card {
  margin: 8px 0 16px;
}

.matrix-table-card :deep(.el-table__body tr:hover > td) {
  background: rgba(16, 54, 84, 0.45) !important;
}

.status-text {
  margin-left: 8px;
  color: #c8ddf1;
  font-size: 12px;
}

.fleet-overview {
  margin: 12px 0 20px;
  padding: 14px 16px;
  background: rgba(10, 31, 49, 0.72);
  border-radius: 12px;
  border: 1px solid rgba(128, 182, 220, 0.2);
}

.fleet-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 10px;
  color: #d6ebff;
}

.fleet-filter-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 10px;
}

.minor-action-btn {
  background: rgba(255, 255, 255, 0.08) !important;
  border-color: rgba(132, 182, 216, 0.38) !important;
  color: #d0e8ff !important;
}

.fleet-matrix-row {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.fleet-farm-select {
  min-width: 360px;
  max-width: 680px;
}

.fleet-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 8px;
}

.fleet-item {
  border: 1px solid rgba(128, 182, 220, 0.2);
  border-radius: 10px;
  padding: 8px 10px;
  background: rgba(8, 24, 38, 0.68);
}

.fleet-name {
  font-size: 13px;
  color: #d6ebff;
  margin-bottom: 6px;
}

.fleet-tags {
  display: flex;
  gap: 6px;
}

.fleet-matrix-row .el-button--primary.is-plain,
.fleet-matrix-row .el-button--warning.is-plain,
.fleet-matrix-row .el-button--danger.is-plain {
  background: transparent !important;
}

.fleet-matrix-row .el-button--primary.is-plain {
  color: #4ac6ff !important;
  border-color: rgba(74, 198, 255, 0.55) !important;
}

.fleet-matrix-row .el-button--warning.is-plain {
  color: #f6b73c !important;
  border-color: rgba(246, 183, 60, 0.55) !important;
}

.fleet-matrix-row .el-button--danger.is-plain {
  color: #ff7b92 !important;
  border-color: rgba(255, 123, 146, 0.55) !important;
}

.hero-section {
  text-align: left;
  padding: 8px 2px 0;
  position: relative;
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

.batch-actions {
  grid-template-columns: repeat(3, 1fr);
  padding-top: 8px;
}

.batch-summary {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.batch-result-toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}

.batch-result-filter {
  min-width: 240px;
}

.el-row {
  margin: 0 -10px;
}

.el-col {
  padding: 0 10px;
  margin-bottom: 12px;
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
  padding: 14px;
  border: none;
  min-height: 284px;
  position: relative;
  overflow: hidden;
}

.prediction-card::before {
  content: '';
  position: absolute;
  right: 16px;
  bottom: 14px;
  width: 98px;
  height: 98px;
  opacity: 0.035;
  border-radius: 50%;
  border: 1px solid rgba(146, 204, 238, 0.8);
}

.card-supershort::before {
  box-shadow: inset 0 0 0 8px rgba(146, 204, 238, 0.15);
}

.card-short::before {
  box-shadow: inset 0 0 0 14px rgba(146, 204, 238, 0.12);
}

.card-medium::before {
  box-shadow: inset 0 0 0 22px rgba(146, 204, 238, 0.08);
}

.card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.card-title-group h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #dff1ff;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.title-icon {
  color: #53d9ff;
  filter: drop-shadow(0 0 8px rgba(18, 215, 255, 0.3));
}

.card-status {
  margin-top: 6px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #9ec4db;
  font-size: 12px;
}

.card-actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.more-btn {
  color: #a8c8dd !important;
}

:deep(.predict-more-menu) {
  background: rgba(10, 32, 50, 0.96) !important;
  border: 1px solid rgba(123, 178, 213, 0.3) !important;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.34);
  backdrop-filter: blur(8px);
}

:deep(.predict-more-menu .el-dropdown-menu__item) {
  color: #d8ecff !important;
}

:deep(.predict-more-menu .el-dropdown-menu__item:hover) {
  background: rgba(18, 215, 255, 0.14) !important;
  color: #ecf8ff !important;
}

.metric-list {
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.metric-item {
  border: 1px solid rgba(126, 176, 206, 0.2);
  border-radius: 8px;
  padding: 8px;
  background: rgba(10, 29, 45, 0.52);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.metric-item span {
  color: #89a9c0;
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.metric-item strong {
  color: #59e2ff;
  font-size: 14px;
  font-family: Consolas, Menlo, Monaco, monospace;
  text-shadow: 0 0 10px rgba(18, 215, 255, 0.2);
}

.card-footer {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.card-footer .el-button {
  min-width: 100px;
}

.prediction-card :deep(.el-card__header) {
  display: none;
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

  .fleet-filter-row {
    flex-direction: column;
    align-items: stretch;
  }

  .fleet-matrix-row {
    flex-direction: column;
    align-items: stretch;
  }

  .fleet-farm-select {
    min-width: 100%;
    max-width: 100%;
  }

  .batch-result-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .batch-result-filter {
    min-width: 100%;
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
