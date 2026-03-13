<template>
  <div class="alarm-center page-shell">
    <div class="page-header">
      <div>
        <h2>统一告警中心</h2>
        <p>当前页面已接入后端告警实体、确认/关闭操作和通知记录，并继续订阅 WebSocket 实时消息。</p>
      </div>
      <el-tag :type="connectionTagType" effect="dark">{{ connectionLabel }}</el-tag>
    </div>

    <el-card class="card-shell">
      <div class="toolbar">
        <el-switch v-model="enableSound" active-text="严重告警播放提示音" />
        <el-switch v-model="enableSms" active-text="显示短信通知记录" />
        <el-select v-model="statusFilter" placeholder="告警状态" class="toolbar-select">
          <el-option label="全部状态" value="all" />
          <el-option label="待处理" value="open" />
          <el-option label="已确认" value="acked" />
          <el-option label="已关闭" value="closed" />
        </el-select>
        <el-button :loading="loading" @click="refresh">刷新</el-button>
      </div>

      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="warning"
        :closable="false"
        show-icon
        class="result-alert"
      />

      <div class="stats">
        <div class="stat danger">
          <div class="label">严重告警</div>
          <div class="value">{{ dangerCount }}</div>
        </div>
        <div class="stat warning">
          <div class="label">预警</div>
          <div class="value">{{ warningCount }}</div>
        </div>
        <div class="stat info">
          <div class="label">通知</div>
          <div class="value">{{ infoCount }}</div>
        </div>
        <div class="stat neutral">
          <div class="label">通知记录</div>
          <div class="value">{{ visibleNotifications.length }}</div>
        </div>
      </div>

      <el-table :data="alerts" border stripe empty-text="暂无告警">
        <el-table-column prop="time" label="告警时间" min-width="170" />
        <el-table-column prop="station" label="场站" min-width="140" />
        <el-table-column label="级别" width="100">
          <template #default="{ row }">
            <el-tag :type="levelTagType(row.level)" effect="dark">{{ levelLabel(row.level) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="module" label="模块" min-width="130" />
        <el-table-column prop="message" label="告警内容" min-width="320" show-overflow-tooltip />
        <el-table-column label="通知策略" min-width="220">
          <template #default="{ row }">
            <span>{{ notificationText(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button
              type="primary"
              link
              :disabled="row.status !== 'open'"
              @click="handleAck(row)"
            >
              确认
            </el-button>
            <el-button
              type="danger"
              link
              :disabled="row.status === 'closed'"
              @click="handleClose(row)"
            >
              关闭
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="notification-panel">
        <div class="panel-title">最近通知记录</div>
        <el-table :data="visibleNotifications" border size="small" empty-text="暂无通知记录">
          <el-table-column prop="occurredAt" label="时间" min-width="160" />
          <el-table-column prop="channel" label="渠道" width="100" />
          <el-table-column prop="status" label="状态" width="100" />
          <el-table-column prop="message" label="内容" min-width="320" show-overflow-tooltip />
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<script>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ackAlarm, closeAlarm, getAlarmNotifications, getAlarms } from '../api/systemApi'
import websocketService from '../services/websocketService'
import farmService from '../utils/farmService'

function toDisplayTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('zh-CN', { hour12: false })
}

function inferLevel(text = '') {
  const content = String(text).toLowerCase()
  if (content.includes('error') || content.includes('failed') || content.includes('exception') || content.includes('告警')) {
    return 'danger'
  }
  if (content.includes('warn') || content.includes('warning') || content.includes('预警')) {
    return 'warning'
  }
  return 'info'
}

function parseBackendAlarm(row, currentFarmCode) {
  if (!row) return null
  return {
    id: row.id,
    time: toDisplayTime(row.occurred_at),
    rawTime: row.occurred_at || Date.now(),
    station: row.farm_code || currentFarmCode || '系统级',
    level: row.level || 'info',
    status: row.status || 'open',
    module: row.module || row.source || 'alarm-service',
    message: row.message || '',
    source: row.source || 'alarm-service',
    notifySound: Boolean(row.notify_sound),
    notifySms: Boolean(row.notify_sms),
    acknowledgedBy: row.acknowledged_by || '',
    closedBy: row.closed_by || ''
  }
}

function parseRealtimeAlert(payload, currentFarmCode) {
  if (!payload) return null
  const timestamp = payload.timestamp || Date.now()
  return {
    id: `rt-${payload.id || timestamp}`,
    time: toDisplayTime(timestamp),
    rawTime: timestamp,
    station: payload.farm_code || payload.station || currentFarmCode || '实时事件',
    level: payload.level || inferLevel(payload.message || payload.details),
    status: 'open',
    module: payload.module || payload.source || 'websocket',
    message: payload.message || payload.details || JSON.stringify(payload),
    source: 'websocket',
    notifySound: payload.level === 'danger' || inferLevel(payload.message || payload.details) === 'danger',
    notifySms: false
  }
}

export default {
  name: 'AlarmCenter',
  setup() {
    const enableSound = ref(true)
    const enableSms = ref(false)
    const statusFilter = ref('all')
    const loading = ref(false)
    const errorMessage = ref('')
    const alerts = ref([])
    const notifications = ref([])
    const connected = ref(false)

    const dangerCount = computed(() => alerts.value.filter(item => item.level === 'danger').length)
    const warningCount = computed(() => alerts.value.filter(item => item.level === 'warning').length)
    const infoCount = computed(() => alerts.value.filter(item => item.level === 'info').length)

    const connectionLabel = computed(() => (connected.value ? '实时通道已连接' : '仅展示后端告警列表'))
    const connectionTagType = computed(() => (connected.value ? 'success' : 'info'))

    const visibleNotifications = computed(() => {
      const rows = enableSms.value
        ? notifications.value
        : notifications.value.filter(item => item.channel !== 'sms')
      return rows.slice(0, 20)
    })

    const levelLabel = (level) => {
      if (level === 'danger') return '严重'
      if (level === 'warning') return '预警'
      return '通知'
    }

    const levelTagType = (level) => {
      if (level === 'danger') return 'danger'
      if (level === 'warning') return 'warning'
      return 'info'
    }

    const statusLabel = (status) => {
      if (status === 'acked') return '已确认'
      if (status === 'closed') return '已关闭'
      return '待处理'
    }

    const statusTagType = (status) => {
      if (status === 'acked') return 'warning'
      if (status === 'closed') return 'info'
      return 'danger'
    }

    const notificationText = (row) => {
      const items = []
      if (row.notifySound) items.push('提示音')
      if (row.notifySms) items.push('短信')
      return items.length > 0 ? items.join(' + ') : '仅页面展示'
    }

    const playBeep = () => {
      if (!enableSound.value || dangerCount.value === 0) return
      try {
        const AudioCtor = window.AudioContext || window.webkitAudioContext
        if (!AudioCtor) return
        const ctx = new AudioCtor()
        const oscillator = ctx.createOscillator()
        const gain = ctx.createGain()
        oscillator.type = 'square'
        oscillator.frequency.value = 880
        gain.gain.value = 0.04
        oscillator.connect(gain)
        gain.connect(ctx.destination)
        oscillator.start()
        oscillator.stop(ctx.currentTime + 0.2)
      } catch (error) {
        console.warn('播放告警音失败', error)
      }
    }

    const mergeAlerts = (incoming = []) => {
      const dedupe = new Map()
      ;[...incoming, ...alerts.value].forEach((item) => {
        if (!item) return
        dedupe.set(String(item.id), item)
      })

      alerts.value = Array.from(dedupe.values())
        .filter(item => statusFilter.value === 'all' || item.status === statusFilter.value)
        .sort((a, b) => String(b.rawTime).localeCompare(String(a.rawTime)))
        .slice(0, 100)
    }

    const loadNotifications = async () => {
      const response = await getAlarmNotifications()
      const rows = Array.isArray(response.data) ? response.data : []
      notifications.value = rows.map((item) => ({
        ...item,
        occurredAt: toDisplayTime(item.occurred_at)
      }))
    }

    const loadAlarms = async () => {
      loading.value = true
      errorMessage.value = ''
      try {
        const params = statusFilter.value === 'all' ? {} : { status: statusFilter.value }
        const response = await getAlarms(params)
        const currentFarmCode = farmService.getCurrentFarm()
        const rows = Array.isArray(response.data) ? response.data : []
        alerts.value = rows.map((row) => parseBackendAlarm(row, currentFarmCode)).filter(Boolean)
        await loadNotifications()
      } catch (error) {
        console.error('加载告警列表失败:', error)
        alerts.value = []
        notifications.value = []
        errorMessage.value = error.response?.data?.error || '加载告警列表失败'
        ElMessage.error(errorMessage.value)
      } finally {
        loading.value = false
      }
    }

    const handleRealtimeAlert = async (payload) => {
      const alert = parseRealtimeAlert(payload, farmService.getCurrentFarm())
      if (!alert) return
      mergeAlerts([alert])
      if (alert.level === 'danger') {
        playBeep()
      }
      try {
        await loadNotifications()
      } catch (error) {
        console.warn('刷新通知记录失败', error)
      }
    }

    const handleConnected = () => {
      connected.value = true
    }

    const handleDisconnected = () => {
      connected.value = false
    }

    const connectRealtime = async () => {
      try {
        await websocketService.connect()
        await websocketService.subscribeToCurrentFarm()
        connected.value = true
      } catch (error) {
        connected.value = false
        console.warn('告警中心未建立实时连接，将继续展示后端告警列表', error)
      }
    }

    const refresh = async () => {
      await loadAlarms()
      playBeep()
    }

    const handleAck = async (row) => {
      try {
        await ackAlarm(row.id)
        ElMessage.success('告警已确认')
        await loadAlarms()
      } catch (error) {
        ElMessage.error(error.response?.data?.error || '确认告警失败')
      }
    }

    const handleClose = async (row) => {
      try {
        await closeAlarm(row.id)
        ElMessage.success('告警已关闭')
        await loadAlarms()
      } catch (error) {
        ElMessage.error(error.response?.data?.error || '关闭告警失败')
      }
    }

    onMounted(async () => {
      await loadAlarms()

      websocketService.on('connection:connected', handleConnected)
      websocketService.on('connection:reconnected', handleConnected)
      websocketService.on('connection:disconnected', handleDisconnected)
      websocketService.on('log:received', handleRealtimeAlert)
      websocketService.on('farm:alert:received', handleRealtimeAlert)

      await connectRealtime()
    })

    onUnmounted(() => {
      websocketService.off('connection:connected', handleConnected)
      websocketService.off('connection:reconnected', handleConnected)
      websocketService.off('connection:disconnected', handleDisconnected)
      websocketService.off('log:received', handleRealtimeAlert)
      websocketService.off('farm:alert:received', handleRealtimeAlert)
    })

    return {
      enableSound,
      enableSms,
      statusFilter,
      loading,
      errorMessage,
      alerts,
      dangerCount,
      warningCount,
      infoCount,
      visibleNotifications,
      connectionLabel,
      connectionTagType,
      levelLabel,
      levelTagType,
      statusLabel,
      statusTagType,
      notificationText,
      refresh,
      handleAck,
      handleClose
    }
  }
}
</script>

<style scoped>
.alarm-center {
  min-height: 100%;
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  color: var(--text-primary);
}

.page-header p {
  margin: 8px 0 0;
  color: var(--text-secondary);
}

.card-shell {
  background: rgba(6, 21, 34, 0.86);
  border: 1px solid rgba(130, 178, 212, 0.2);
}

.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.toolbar-select {
  width: 140px;
}

.result-alert {
  margin-bottom: 12px;
}

.stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.stat {
  border-radius: 10px;
  padding: 12px;
  border: 1px solid rgba(130, 178, 212, 0.2);
}

.stat .label {
  color: var(--text-secondary);
  font-size: 12px;
}

.stat .value {
  color: var(--text-primary);
  font-size: 24px;
  margin-top: 4px;
  font-weight: 700;
}

.stat.danger {
  background: rgba(160, 32, 32, 0.22);
}

.stat.warning {
  background: rgba(165, 115, 30, 0.2);
}

.stat.info {
  background: rgba(26, 83, 126, 0.22);
}

.stat.neutral {
  background: rgba(51, 65, 85, 0.28);
}

.notification-panel {
  margin-top: 16px;
}

.panel-title {
  margin-bottom: 10px;
  color: var(--text-primary);
  font-weight: 600;
}

@media (max-width: 960px) {
  .page-header {
    flex-direction: column;
  }

  .stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .stats {
    grid-template-columns: 1fr;
  }
}
</style>
