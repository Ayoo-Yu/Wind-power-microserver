
<template>
  <div class="weather-data-fetcher page-shell">
    <div class="gradient-background"></div>

    <div class="page-header">
      <h1 class="page-title">气象预报数据拉取</h1>
      <p class="page-description">通道配置、任务调度与数据到达质量管理</p>
    </div>

    <div class="meta-updated">调度器状态更新时间：{{ schedulerCheckedAt || '--' }}</div>

    <el-card class="flow-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span class="card-title">今日系统气象健康大盘</span>
          <div class="button-group">
            <el-button type="info" size="small" :loading="checkingScheduler" @click="checkSchedulerStatus">刷新状态</el-button>
            <el-button v-if="!schedulerInfo.managed_externally" type="warning" size="small" :loading="restartingScheduler" @click="restartScheduler">重启调度器</el-button>
          </div>
        </div>
      </template>

      <div class="health-grid">
        <div class="health-node" :class="`is-${healthBoard.channel.status}`">
          <div class="health-name">通道状态</div>
          <div class="health-text">{{ healthBoard.channel.text }}</div>
        </div>
        <div class="health-node" :class="`is-${healthBoard.scheduler.status}`">
          <div class="health-name">定时任务</div>
          <div class="health-text">{{ healthBoard.scheduler.text }}</div>
        </div>
        <div class="health-node health-node-ring" :class="`is-${healthBoard.arrival.status}`">
          <div class="health-name">今日数据到达率</div>
          <el-progress type="dashboard" :percentage="healthBoard.arrival.percent" :stroke-width="10" :color="healthBoard.arrival.color">
            <template #default>
              <div class="ring-center">{{ healthBoard.arrival.ready }}/{{ healthBoard.arrival.total }}</div>
            </template>
          </el-progress>
          <div class="health-text">{{ healthBoard.arrival.text }}</div>
        </div>
        <div class="health-node" :class="`is-${healthBoard.parse.status}`">
          <div class="health-name">文件校验</div>
          <div class="health-text">{{ healthBoard.parse.text }}</div>
        </div>
      </div>
    </el-card>

    <EcmwfStatusCard :status="ecmwfStatus" :loading="loadingEcmwf" @refresh="refreshEcmwfStatus" />

    <el-card class="config-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span class="card-title">SFTP 数据源通道配置</span>
          <el-button type="primary" size="small" @click="openConnectionDialog">添加连接</el-button>
        </div>
      </template>

      <el-table :data="connections" style="width: 100%" v-loading="loadingConnections">
        <el-table-column prop="name" label="连接名称" min-width="120" align="center" />
        <el-table-column prop="farm_code" label="归属场站" min-width="110" align="center" />
        <el-table-column prop="host" label="服务器地址" min-width="170" align="center" />
        <el-table-column prop="port" label="端口" width="80" align="center" />
        <el-table-column prop="username" label="用户名" min-width="100" align="center" />
        <el-table-column label="验证状态" min-width="130" align="center">
          <template #default="scope">
            <el-tag :type="getConnectionStatusTag(scope.row).type">
              {{ getConnectionStatusTag(scope.row).text }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="220" align="center" fixed="right">
          <template #default="scope">
            <div class="button-group">
              <el-button size="small" type="info" :loading="scope.row.testing" @click="testConnection(scope.row)">测试连接</el-button>
              <el-button size="small" type="primary" @click="editConnection(scope.row)">编辑</el-button>
              <el-button size="small" type="danger" @click="deleteConnection(scope.row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="task-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span class="card-title">文件追踪列表</span>
          <el-button type="primary" size="small" @click="openTaskDialog">创建任务</el-button>
        </div>
      </template>

      <el-table :data="tasks" style="width: 100%" v-loading="loadingTasks">
        <el-table-column prop="name" label="任务名称" min-width="130" align="center" />
        <el-table-column prop="farm_code" label="归属场站" min-width="110" align="center" />
        <el-table-column prop="connection_name" label="连接" min-width="120" align="center" />
        <el-table-column label="目标文件规则" min-width="180" align="center">
          <template #default="scope">{{ scope.row.filename_template || scope.row.file_pattern || '-' }}</template>
        </el-table-column>
        <el-table-column label="今日状态" min-width="210" align="center">
          <template #default="scope">
            <el-tag :type="getTodayStatusTag(scope.row).type">{{ getTodayStatusTag(scope.row).text }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="执行频率" min-width="120" align="center">
          <template #default="scope">{{ getScheduleDescription(scope.row.schedule) }}</template>
        </el-table-column>
        <el-table-column label="最后执行" min-width="150" align="center">
          <template #default="scope">{{ formatDateTime(scope.row.last_run) }}</template>
        </el-table-column>
        <el-table-column label="操作" min-width="350" align="center" fixed="right">
          <template #default="scope">
            <div class="action-buttons-container">
              <el-button size="small" type="info" :loading="scope.row.running" @click="runTask(scope.row)">手动触发一次</el-button>
              <el-button size="small" type="primary" @click="viewTaskLogs(scope.row)">查看任务日志</el-button>
              <el-button size="small" :type="scope.row.enabled ? 'warning' : 'success'" @click="toggleTask(scope.row)">
                {{ scope.row.enabled ? '停用' : '启用' }}
              </el-button>
              <el-button size="small" type="primary" plain @click="editTask(scope.row)">编辑</el-button>
              <el-button size="small" type="danger" plain @click="deleteTask(scope.row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showConnectionDialog" :title="editingConnection ? '编辑 SFTP 数据源通道' : '添加 SFTP 数据源通道'" width="640px">
      <el-form :model="connectionForm" :rules="connectionRules" ref="connectionFormRef" label-width="130px">
        <el-form-item label="连接名称" prop="name"><el-input v-model="connectionForm.name" placeholder="例如：省调中心SFTP" /></el-form-item>
        <el-form-item label="归属场站" prop="farm_code">
          <el-select v-model="connectionForm.farm_code" placeholder="请选择场站" filterable>
            <el-option v-for="farm in farms" :key="farm.farm_code" :label="farm.farm_name" :value="farm.farm_code" />
          </el-select>
        </el-form-item>
        <el-form-item label="服务器地址" prop="host"><el-input v-model="connectionForm.host" placeholder="IP地址或域名" /></el-form-item>
        <el-form-item label="端口" prop="port"><el-input-number v-model="connectionForm.port" :min="1" :max="65535" /></el-form-item>
        <el-form-item label="用户名" prop="username"><el-input v-model="connectionForm.username" placeholder="用户名" /></el-form-item>
        <el-form-item label="认证方式" prop="auth_type">
          <el-radio-group v-model="connectionForm.auth_type"><el-radio value="password">密码认证</el-radio><el-radio value="key">密钥认证</el-radio></el-radio-group>
        </el-form-item>
        <el-form-item v-if="connectionForm.auth_type === 'password'" label="密码" prop="password">
          <el-input
            v-model="connectionForm.password"
            type="password"
            show-password
            :placeholder="connectionForm.password_set ? '已配置，留空表示保持原密码' : '请输入密码'"
          />
        </el-form-item>
        <el-form-item v-if="connectionForm.auth_type === 'key'" label="私钥路径" prop="private_key_path"><el-input v-model="connectionForm.private_key_path" placeholder="/home/user/.ssh/id_rsa" /></el-form-item>
        <el-form-item v-if="connectionForm.auth_type === 'key'" label="私钥密码" prop="key_passphrase">
          <el-input
            v-model="connectionForm.key_passphrase"
            type="password"
            show-password
            :placeholder="connectionForm.key_passphrase_set ? '已配置，留空表示保持原口令' : '无口令时可留空'"
          />
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="showConnectionDialog = false">取消</el-button><el-button type="primary" :loading="savingConnection" @click="saveConnection">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="showTaskDialog" :title="editingTask ? '编辑任务配置' : '创建任务配置'" width="760px">
      <el-form :model="taskForm" :rules="taskRules" ref="taskFormRef" label-width="160px">
        <el-form-item label="任务名称" prop="name"><el-input v-model="taskForm.name" placeholder="任务名称" /></el-form-item>
        <el-form-item label="归属场站" prop="farm_code">
          <el-select v-model="taskForm.farm_code" placeholder="请选择场站" filterable>
            <el-option v-for="farm in farms" :key="farm.farm_code" :label="farm.farm_name" :value="farm.farm_code" />
          </el-select>
        </el-form-item>
        <el-form-item label="数据源通道" prop="connection_id">
          <el-select v-model="taskForm.connection_id" placeholder="选择连接" filterable>
            <el-option v-for="conn in connections" :key="conn.id" :label="`${conn.name} (${conn.farm_code || '-'})`" :value="conn.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="远程目录路径" prop="remote_path"><el-input v-model="taskForm.remote_path" placeholder="/weather_data/export/" /></el-form-item>
        <el-form-item label="时间目录格式" prop="path_pattern">
          <el-select v-model="taskForm.path_pattern" placeholder="请选择目录结构">
            <el-option label="文件直接位于远程目录" value="flat" />
            <el-option label="YYYY_MMDDHHNN" value="YYYY_MMDDHHNN" />
            <el-option label="YYYYMMDDHH" value="YYYYMMDDHH" />
            <el-option label="YYYY-MM-DD/HH" value="YYYY-MM-DD/HH" />
            <el-option label="自定义" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="taskForm.path_pattern === 'custom'" label="自定义目录格式" prop="custom_path_pattern">
          <el-input v-model="taskForm.custom_path_pattern" placeholder="YYYY/MM/DD/HH" />
        </el-form-item>
        <el-form-item label="文件名动态匹配模板" prop="filename_template">
          <el-input v-model="taskForm.filename_template" placeholder="NWP_${YYYYMMDD}.csv" />
          <el-text size="small" type="info">支持模板：`${YYYYMMDD}`、`${YYYYMMDDHH}`、通配符 `*`</el-text>
        </el-form-item>
        <el-form-item label="执行频率" prop="schedule">
          <el-select v-model="taskForm.schedule" placeholder="选择执行频率">
            <el-option label="每小时" value="0 * * * *" /><el-option label="每6小时" value="0 */6 * * *" /><el-option label="每12小时" value="0 */12 * * *" /><el-option label="每天" value="0 0 * * *" /><el-option label="自定义" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="taskForm.schedule === 'custom'" label="Cron表达式" prop="custom_schedule"><el-input v-model="taskForm.custom_schedule" placeholder="0 10 * * *" /></el-form-item>
        <el-form-item label="本地保存路径" prop="save_path"><el-input v-model="taskForm.save_path" placeholder="/data/weather/{date}/" /></el-form-item>
        <el-form-item label="超时时间(秒)" prop="timeout"><el-input-number v-model="taskForm.timeout" :min="30" :max="3600" /></el-form-item>
        <el-form-item label="重试次数" prop="retry_count"><el-input-number v-model="taskForm.retry_count" :min="0" :max="5" /></el-form-item>
        <el-form-item label="任务描述" prop="description"><el-input v-model="taskForm.description" type="textarea" :rows="3" placeholder="可填写任务说明" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="showTaskDialog = false">取消</el-button><el-button type="primary" :loading="savingTask" @click="saveTask">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="showLogsDialog" title="气象文件任务日志" width="1000px" :close-on-click-modal="false">
      <div class="logs-header">
        <div class="logs-title"><strong>{{ currentTaskName }}</strong> 的任务日志</div>
        <div class="logs-filters">
          <el-select v-model="logLevel" @change="fetchTaskLogs" size="small" style="width: 120px">
            <el-option label="全部" value="" /><el-option label="信息" value="info" /><el-option label="成功" value="success" /><el-option label="警告" value="warning" /><el-option label="错误" value="error" />
          </el-select>
          <el-button size="small" type="primary" :loading="loadingLogs" @click="fetchTaskLogs">刷新</el-button>
        </div>
      </div>

      <div class="logs-content" v-loading="loadingLogs">
        <el-empty v-if="taskLogs.length === 0" description="暂无日志记录" />
        <div v-else class="logs-list">
          <div v-for="log in taskLogs" :key="log.id" :class="['log-item', `log-${log.level}`]">
            <div class="log-header-line"><el-tag :type="getLogLevelType(log.level)" size="small">{{ getLogLevelText(log.level) }}</el-tag><span class="log-time">{{ formatDateTime(log.created_at) }}</span></div>
            <div class="log-message">{{ log.message }}</div>
            <div v-if="log.details" class="log-details">{{ log.details }}</div>
          </div>
        </div>
      </div>
      <template #footer><el-button @click="showLogsDialog = false">关闭</el-button></template>
    </el-dialog>
  </div>
</template>

<script>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import EcmwfStatusCard from './EcmwfStatusCard.vue'
import {
  getWeatherConnections,
  getWeatherTasks,
  createWeatherConnection,
  updateWeatherConnection,
  testWeatherConnection,
  deleteWeatherConnection,
  runWeatherTask,
  toggleWeatherTask,
  createWeatherTask,
  updateWeatherTask,
  deleteWeatherTask,
  getWeatherTaskLogs,
  getWeatherSchedulerStatus,
  restartWeatherScheduler,
  getEcmwfAvailability,
  getEcmwfLatest
} from '../api/weatherFetchApi'
import { getFarms } from '../api/farmApi'

function extractErrorMessage(error, fallback) {
  return error?.response?.data?.message || error?.response?.data?.error || fallback
}

export default {
  name: 'WeatherDataFetcher',
  components: { EcmwfStatusCard },
  setup() {
    const farms = ref([])
    const connections = ref([])
    const tasks = ref([])
    const taskLogs = ref([])

    const loadingConnections = ref(false)
    const loadingTasks = ref(false)
    const loadingLogs = ref(false)
    const savingConnection = ref(false)
    const savingTask = ref(false)
    const checkingScheduler = ref(false)
    const restartingScheduler = ref(false)

    const showConnectionDialog = ref(false)
    const showTaskDialog = ref(false)
    const showLogsDialog = ref(false)
    const editingConnection = ref(false)
    const editingTask = ref(false)

    const connectionFormRef = ref(null)
    const taskFormRef = ref(null)

    const currentTaskId = ref(null)
    const currentTaskName = ref('')
    const logLevel = ref('')
    const schedulerInfo = ref({ is_running: false, jobs: [], total_jobs: 0 })
    const schedulerCheckedAt = ref('')

    // ECMWF 数据库状态
    const ecmwfStatus = ref(null)
    const loadingEcmwf = ref(false)

    const refreshEcmwfStatus = async () => {
      loadingEcmwf.value = true
      try {
        const today = new Date().toISOString().slice(0, 10)
        const farmCode = connectionForm.farm_code || farms.value[0]?.farm_code || ''
        const [availRes, latestRes] = await Promise.all([
          getEcmwfAvailability({ farm_code: farmCode, date: today }),
          getEcmwfLatest({ farm_code: farmCode, data_type: 'DQ' }),
        ])
        const avail = availRes.data?.data?.availability || {}
        const latest = latestRes.data?.data?.latest_timestamp || null
        ecmwfStatus.value = { availability: avail, latest_timestamp: latest ? latest.slice(0, 19) : null }
      } catch (e) {
        console.warn('ECMWF status fetch failed:', e)
        ecmwfStatus.value = { availability: {}, latest_timestamp: null }
      } finally {
        loadingEcmwf.value = false
      }
    }

    const connectionForm = reactive({
      id: null,
      name: '',
      farm_code: '',
      host: '',
      port: 22,
      username: '',
      auth_type: 'password',
      password: '',
      password_set: false,
      private_key_path: '',
      key_passphrase: '',
      key_passphrase_set: false
    })

    const defaultSavePath = '/data/weather/{date}/'

    const taskForm = reactive({
      id: null,
      name: '',
      farm_code: '',
      connection_id: '',
      remote_path: '/weather_data/export/',
      path_pattern: 'flat',
      custom_path_pattern: '',
      filename_template: 'NWP_${YYYYMMDD}.csv',
      schedule: '0 */6 * * *',
      custom_schedule: '',
      save_path: defaultSavePath,
      timeout: 300,
      retry_count: 3,
      description: ''
    })

    const connectionRules = computed(() => {
      const rules = {
        name: [{ required: true, message: '请输入连接名称', trigger: 'blur' }],
        farm_code: [{ required: true, message: '请选择场站', trigger: 'change' }],
        host: [{ required: true, message: '请输入服务器地址', trigger: 'blur' }],
        username: [{ required: true, message: '请输入用户名', trigger: 'blur' }]
      }
      if (connectionForm.auth_type === 'password' && !connectionForm.password_set) {
        rules.password = [{ required: true, message: '请输入密码', trigger: 'blur' }]
      }
      if (connectionForm.auth_type === 'key') {
        rules.private_key_path = [{ required: true, message: '请输入私钥路径', trigger: 'blur' }]
      }
      return rules
    })

    const taskRules = computed(() => {
      const rules = {
        name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }],
        farm_code: [{ required: true, message: '请选择场站', trigger: 'change' }],
        connection_id: [{ required: true, message: '请选择连接', trigger: 'change' }],
        remote_path: [{ required: true, message: '请输入远程目录路径', trigger: 'blur' }],
        path_pattern: [{ required: true, message: '请选择时间目录格式', trigger: 'change' }],
        filename_template: [{ required: true, message: '请输入文件名动态匹配模板', trigger: 'blur' }],
        save_path: [{ required: true, message: '请输入本地保存路径', trigger: 'blur' }]
      }
      if (taskForm.path_pattern === 'custom') {
        rules.custom_path_pattern = [{ required: true, message: '请输入自定义目录格式', trigger: 'blur' }]
      }
      if (taskForm.schedule === 'custom') {
        rules.custom_schedule = [{ required: true, message: '请输入 Cron 表达式', trigger: 'blur' }]
      }
      return rules
    })

    const isToday = (timeStr) => {
      if (!timeStr) return false
      const d = new Date(timeStr)
      if (Number.isNaN(d.getTime())) return false
      const now = new Date()
      return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate()
    }

    const isRecent = (timeStr, maxAgeHours = 24) => {
      if (!timeStr) return false
      const timestamp = new Date(timeStr).getTime()
      return Number.isFinite(timestamp) && Date.now() - timestamp <= maxAgeHours * 60 * 60 * 1000
    }

    const healthBoard = computed(() => {
      const totalChannels = connections.value.length
      const schedulerManagedExternally = !!schedulerInfo.value?.managed_externally
      const schedulerRunning = schedulerInfo.value?.is_running === true
      const heartbeatStatus = schedulerInfo.value?.heartbeat?.status || 'unknown'
      const enabledTasks = tasks.value.filter((item) => item.enabled)
      const farmKeys = enabledTasks.map((item) => item.farm_code || `task-${item.id}`)
      const totalStations = new Set(farmKeys).size
      const readyStations = new Set(enabledTasks.filter((item) => isToday(item.last_run) && ['success', 'parsed', 'completed'].includes((item.status || '').toLowerCase())).map((item) => item.farm_code || `task-${item.id}`)).size
      const arrivalPercent = totalStations > 0 ? Math.round((readyStations / totalStations) * 100) : 0
      const todayRuns = enabledTasks.filter((item) => isToday(item.last_run))
      const parseOkRuns = todayRuns.filter((item) => ['success', 'parsed', 'completed'].includes((item.status || '').toLowerCase()))
      const parsePercent = todayRuns.length ? Math.round((parseOkRuns.length / todayRuns.length) * 100) : null
      const successfulConnectionIds = new Set(parseOkRuns.map((item) => item.connection_id))
      const connectedChannels = connections.value.filter((item) => (
        successfulConnectionIds.has(item.id) || (item.status === 'connected' && isRecent(item.last_test_at))
      )).length
      const channelOk = totalChannels > 0 && totalChannels === connectedChannels

      let schedulerText = '🔴 未检测到 Celery Beat 心跳'
      if (schedulerRunning) schedulerText = '🟢 Celery Beat 心跳正常'
      else if (heartbeatStatus === 'unavailable') schedulerText = '🔴 Redis 不可用，无法确认调度状态'
      else if (!schedulerManagedExternally) schedulerText = '🔴 调度器已停止'

      const arrivalReady = totalStations > 0 && arrivalPercent >= 90
      const arrivalStatus = totalStations === 0 ? 'warning' : (arrivalReady ? 'ready' : (arrivalPercent >= 60 ? 'warning' : 'danger'))
      const arrivalText = totalStations === 0
        ? '暂无启用的场站任务'
        : `${arrivalReady ? '🟢' : '🔴'} ${readyStations}/${totalStations} 个场站今日已就绪`
      const parseStatus = parsePercent === null ? 'warning' : (parsePercent >= 95 ? 'ready' : (parsePercent >= 70 ? 'warning' : 'danger'))
      const parseText = parsePercent === null
        ? '今日尚无执行记录'
        : (parsePercent === 100 ? '🟢 100% 成功无报错' : `${parsePercent}% 成功`)

      return {
        channel: { status: channelOk ? 'ready' : 'warning', text: channelOk ? '🟢 所有SFTP配置正常' : (totalChannels ? `🔴 存在断连通道 (${connectedChannels}/${totalChannels})` : '尚未配置 SFTP 通道') },
        scheduler: {
          status: schedulerRunning ? 'ready' : 'warning',
          text: schedulerText
        },
        arrival: {
          status: arrivalStatus,
          percent: arrivalPercent,
          ready: readyStations,
          total: totalStations,
          color: arrivalPercent >= 90 ? '#67c23a' : (arrivalPercent >= 60 ? '#e6a23c' : '#f56c6c'),
          text: arrivalText
        },
        parse: { status: parseStatus, text: parseText }
      }
    })

    const formatDateTime = (value) => {
      if (!value) return '--'
      const d = new Date(value)
      if (Number.isNaN(d.getTime())) return String(value)
      return d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
    }

    const formatShortTime = (value) => {
      if (!value) return ''
      const d = new Date(value)
      if (Number.isNaN(d.getTime())) return ''
      return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
    }

    const getTodayStatusTag = (task) => {
      const backendText = task.today_status_text || task.business_status_text
      if (backendText) return { type: task.today_status_type || 'info', text: backendText }
      const status = (task.status || '').toLowerCase()
      const runTime = formatShortTime(task.last_run)
      if (status === 'success' || status === 'parsed' || status === 'completed') return { type: 'success', text: `🟢 已获取并校验${runTime ? ` (${runTime})` : ''}` }
      if (status === 'partial') return { type: 'warning', text: '🟡 部分文件处理失败' }
      if (status === 'error' || status.includes('parse_failed')) return { type: 'danger', text: '🔴 文件处理失败' }
      if (status.includes('not_found')) return { type: 'danger', text: '🔴 文件未找到' }
      if (!task.enabled) return { type: 'info', text: '⏸ 已停用' }
      return { type: 'warning', text: '🟡 等待执行' }
    }

    const getConnectionStatusTag = (connection) => {
      const hasSuccessfulTaskToday = tasks.value.some((task) => (
        task.connection_id === connection.id &&
        isToday(task.last_run) &&
        ['success', 'parsed', 'completed'].includes((task.status || '').toLowerCase())
      ))
      if (hasSuccessfulTaskToday) return { type: 'success', text: '今日任务已验证' }
      if (connection.status === 'connected' && isRecent(connection.last_test_at)) {
        return { type: 'success', text: '24小时内测试通过' }
      }
      return { type: 'warning', text: '等待重新验证' }
    }

    const getScheduleDescription = (cronExpression) => {
      const map = { '0 * * * *': '每小时', '0 */6 * * *': '每6小时', '0 */12 * * *': '每12小时', '0 0 * * *': '每天' }
      return map[cronExpression] || cronExpression || '-'
    }

    const fetchFarms = async () => {
      try {
        const rows = await getFarms()
        farms.value = rows.map((item) => ({ farm_code: item.farm_code || item.code || item.id, farm_name: item.farm_name || item.name || item.farm_code || item.code }))
      } catch {
        farms.value = []
      }
    }

    const fetchConnections = async () => {
      loadingConnections.value = true
      try {
        const response = await getWeatherConnections()
        connections.value = response.data || []
      } catch (error) {
        ElMessage.error(extractErrorMessage(error, '获取连接列表失败'))
      } finally {
        loadingConnections.value = false
      }
    }

    const fetchTasks = async () => {
      loadingTasks.value = true
      try {
        const response = await getWeatherTasks()
        tasks.value = (response.data || []).map((item) => ({ ...item, filename_template: item.filename_template || item.file_pattern }))
      } catch (error) {
        ElMessage.error(extractErrorMessage(error, '获取任务列表失败'))
      } finally {
        loadingTasks.value = false
      }
    }

    const checkSchedulerStatus = async () => {
      checkingScheduler.value = true
      try {
        const response = await getWeatherSchedulerStatus()
        schedulerInfo.value = response.data || { is_running: false, jobs: [], total_jobs: 0 }
        schedulerCheckedAt.value = formatDateTime(new Date())
      } catch (error) {
        schedulerInfo.value = { is_running: false, jobs: [], total_jobs: 0 }
        ElMessage.error(extractErrorMessage(error, '获取调度器状态失败'))
      } finally {
        checkingScheduler.value = false
      }
    }

    const restartScheduler = async () => {
      try {
        await ElMessageBox.confirm('确定重启调度器吗？', '确认重启', { type: 'warning' })
        restartingScheduler.value = true
        await restartWeatherScheduler()
        ElMessage.success('调度器重启成功')
        await checkSchedulerStatus()
        await fetchTasks()
      } catch (error) {
        if (error !== 'cancel') ElMessage.error(extractErrorMessage(error, '重启调度器失败'))
      } finally {
        restartingScheduler.value = false
      }
    }

    const openConnectionDialog = () => {
      editingConnection.value = false
      Object.assign(connectionForm, { id: null, name: '', farm_code: farms.value[0]?.farm_code || '', host: '', port: 22, username: '', auth_type: 'password', password: '', password_set: false, private_key_path: '', key_passphrase: '', key_passphrase_set: false })
      showConnectionDialog.value = true
    }

    const editConnection = (row) => {
      editingConnection.value = true
      Object.assign(connectionForm, { id: row.id, name: row.name, farm_code: row.farm_code || '', host: row.host, port: row.port || 22, username: row.username, auth_type: row.auth_type || 'password', password: '', password_set: Boolean(row.password_set), private_key_path: row.private_key_path || '', key_passphrase: '', key_passphrase_set: Boolean(row.key_passphrase_set) })
      showConnectionDialog.value = true
    }

    const saveConnection = async () => {
      if (!connectionFormRef.value) return
      try {
        await connectionFormRef.value.validate()
        savingConnection.value = true
        const payload = { ...connectionForm }
        delete payload.password_set
        delete payload.key_passphrase_set
        if (!payload.password) delete payload.password
        if (!payload.key_passphrase) delete payload.key_passphrase
        if (editingConnection.value) await updateWeatherConnection(connectionForm.id, payload)
        else await createWeatherConnection(payload)
        ElMessage.success(editingConnection.value ? '连接更新成功' : '连接创建成功')
        showConnectionDialog.value = false
        await fetchConnections()
      } catch (error) {
        ElMessage.error(extractErrorMessage(error, '保存连接失败'))
      } finally {
        savingConnection.value = false
      }
    }

    const deleteConnection = async (row) => {
      try {
        await ElMessageBox.confirm('确定删除该连接吗？', '确认删除', { type: 'warning' })
        await deleteWeatherConnection(row.id)
        ElMessage.success('连接删除成功')
        await fetchConnections()
      } catch (error) {
        if (error !== 'cancel') ElMessage.error(extractErrorMessage(error, '删除连接失败'))
      }
    }

    const testConnection = async (row) => {
      row.testing = true
      try {
        const response = await testWeatherConnection(row.id)
        const success = !!response?.data?.success
        row.status = success ? 'connected' : 'disconnected'
        ElMessage[success ? 'success' : 'error'](success ? '连接测试成功' : '连接测试失败')
      } catch (error) {
        row.status = 'disconnected'
        ElMessage.error(extractErrorMessage(error, '连接测试失败'))
      } finally {
        row.testing = false
      }
    }

    const openTaskDialog = () => {
      editingTask.value = false
      Object.assign(taskForm, { id: null, name: '', farm_code: farms.value[0]?.farm_code || '', connection_id: '', remote_path: '/weather_data/export/', path_pattern: 'flat', custom_path_pattern: '', filename_template: 'NWP_${YYYYMMDD}.csv', schedule: '0 */6 * * *', custom_schedule: '', save_path: defaultSavePath, timeout: 300, retry_count: 3, description: '' })
      showTaskDialog.value = true
    }

    const editTask = (row) => {
      editingTask.value = true
      const schedulePresets = new Set(['0 * * * *', '0 */6 * * *', '0 */12 * * *', '0 0 * * *'])
      const scheduleIsPreset = schedulePresets.has(row.schedule)
      Object.assign(taskForm, { id: row.id, name: row.name, farm_code: row.farm_code || '', connection_id: row.connection_id, remote_path: row.remote_path, path_pattern: row.path_pattern || 'flat', custom_path_pattern: row.custom_path_pattern || '', filename_template: row.filename_template || row.file_pattern || '', schedule: scheduleIsPreset ? row.schedule : 'custom', custom_schedule: scheduleIsPreset ? '' : row.schedule, save_path: row.save_path || defaultSavePath, timeout: row.timeout || 300, retry_count: row.retry_count || 3, description: row.description || '' })
      showTaskDialog.value = true
    }

    const saveTask = async () => {
      if (!taskFormRef.value) return
      try {
        await taskFormRef.value.validate()
        savingTask.value = true
        const payload = { ...taskForm, file_pattern: taskForm.filename_template, schedule: taskForm.schedule === 'custom' ? taskForm.custom_schedule : taskForm.schedule, time_strategy: 'latest', processing_options: ['integrity_check'], deduplication_options: ['skip_existing'] }
        if (editingTask.value) await updateWeatherTask(taskForm.id, payload)
        else await createWeatherTask(payload)
        ElMessage.success(editingTask.value ? '任务更新成功' : '任务创建成功')
        showTaskDialog.value = false
        await fetchTasks()
      } catch (error) {
        ElMessage.error(extractErrorMessage(error, '保存任务失败'))
      } finally {
        savingTask.value = false
      }
    }

    const deleteTask = async (row) => {
      try {
        await ElMessageBox.confirm('确定删除该任务吗？', '确认删除', { type: 'warning' })
        await deleteWeatherTask(row.id)
        ElMessage.success('任务删除成功')
        await fetchTasks()
      } catch (error) {
        if (error !== 'cancel') ElMessage.error(extractErrorMessage(error, '删除任务失败'))
      }
    }

    const runTask = async (row) => {
      row.running = true
      try {
        await runWeatherTask(row.id)
        ElMessage.success('任务已触发')
        await fetchTasks()
      } catch (error) {
        ElMessage.error(extractErrorMessage(error, '触发任务失败'))
      } finally {
        row.running = false
      }
    }

    const toggleTask = async (row) => {
      try {
        await toggleWeatherTask(row.id)
        ElMessage.success(row.enabled ? '任务已停用' : '任务已启用')
        await fetchTasks()
      } catch (error) {
        ElMessage.error(extractErrorMessage(error, '切换任务状态失败'))
      }
    }

    const viewTaskLogs = (row) => {
      currentTaskId.value = row.id
      currentTaskName.value = row.name
      showLogsDialog.value = true
      fetchTaskLogs()
    }

    const fetchTaskLogs = async () => {
      if (!currentTaskId.value) return
      loadingLogs.value = true
      try {
        const response = await getWeatherTaskLogs(currentTaskId.value, { level: logLevel.value || undefined, per_page: 100 })
        taskLogs.value = response?.data?.logs || []
      } catch (error) {
        taskLogs.value = []
        ElMessage.error(extractErrorMessage(error, '获取日志失败'))
      } finally {
        loadingLogs.value = false
      }
    }

    const getLogLevelType = (level) => (level === 'success' ? 'success' : level === 'warning' ? 'warning' : level === 'error' ? 'danger' : 'info')
    const getLogLevelText = (level) => (level === 'success' ? '成功' : level === 'warning' ? '警告' : level === 'error' ? '错误' : '信息')

    onMounted(async () => {
      await Promise.all([fetchFarms(), fetchConnections(), fetchTasks(), checkSchedulerStatus()])
      refreshEcmwfStatus()
      if (!connectionForm.farm_code) connectionForm.farm_code = farms.value[0]?.farm_code || ''
      if (!taskForm.farm_code) taskForm.farm_code = farms.value[0]?.farm_code || ''
    })

    return {
      farms, connections, tasks, taskLogs,
      loadingConnections, loadingTasks, loadingLogs, savingConnection, savingTask, checkingScheduler, restartingScheduler,
      showConnectionDialog, showTaskDialog, showLogsDialog, editingConnection, editingTask,
      connectionFormRef, taskFormRef,
      connectionForm, taskForm, connectionRules, taskRules,
      currentTaskName, logLevel, schedulerCheckedAt, schedulerInfo, healthBoard,
      ecmwfStatus, loadingEcmwf, refreshEcmwfStatus,
      checkSchedulerStatus, restartScheduler, openConnectionDialog, editConnection, saveConnection, deleteConnection, testConnection,
      openTaskDialog, editTask, saveTask, deleteTask, runTask, toggleTask,
      viewTaskLogs, fetchTaskLogs, getLogLevelType, getLogLevelText,
      formatDateTime, getScheduleDescription, getTodayStatusTag, getConnectionStatusTag
    }
  }
}
</script>

<style scoped>
.weather-data-fetcher { position: relative; min-height: 100vh; padding: 20px; }
.page-header { text-align: center; margin-bottom: 14px; }
.page-title { margin: 0 0 6px; color: var(--text-primary); }
.page-description { margin: 0; color: var(--text-secondary); }
.meta-updated { margin-bottom: 12px; color: var(--text-secondary); font-size: 12px; font-family: Consolas, "Roboto Mono", monospace; }
.card-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.card-title { font-weight: 600; color: var(--text-primary); font-size: 16px; }
.health-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.health-node { border: 1px solid rgba(146, 186, 220, 0.25); border-radius: 12px; background: rgba(8, 24, 38, 0.58); padding: 12px; min-height: 100px; }
.health-name { color: var(--text-primary); font-size: 13px; font-weight: 600; margin-bottom: 6px; }
.health-text { color: var(--text-secondary); font-size: 12px; }
.health-node-ring { display: flex; flex-direction: column; align-items: center; }
.ring-center { font-size: 14px; font-weight: 600; }
.health-node.is-ready { box-shadow: inset 0 0 0 1px rgba(103, 194, 58, 0.4); }
.health-node.is-warning { box-shadow: inset 0 0 0 1px rgba(230, 162, 60, 0.4); }
.health-node.is-danger { box-shadow: inset 0 0 0 1px rgba(245, 108, 108, 0.4); }
.button-group { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.action-buttons-container { display: flex; align-items: center; gap: 6px; justify-content: center; flex-wrap: wrap; }
.logs-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.logs-filters { display: flex; gap: 8px; align-items: center; }
.logs-content { max-height: 600px; overflow-y: auto; }
.logs-list { display: flex; flex-direction: column; gap: 8px; }
.log-item { padding: 12px 16px; border-radius: 8px; border-left: 4px solid #409eff; background: rgba(8, 24, 38, 0.65); }
.log-item.log-success { border-left-color: #67c23a; }
.log-item.log-warning { border-left-color: #e6a23c; }
.log-item.log-error { border-left-color: #f56c6c; }
.log-header-line { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.log-time { font-size: 12px; color: var(--text-muted); font-family: Consolas, "Roboto Mono", monospace; }
.log-message { color: var(--text-primary); font-size: 14px; margin-bottom: 4px; }
.log-details { color: var(--text-secondary); font-size: 12px; white-space: pre-wrap; word-break: break-word; }
@media (max-width: 1200px) { .health-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 768px) { .weather-data-fetcher { padding: 14px; } .health-grid { grid-template-columns: 1fr; } }
</style>
