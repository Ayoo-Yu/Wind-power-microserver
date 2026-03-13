<template>
  <div class="alarm-center page-shell">
    <div class="page-header">
      <div>
        <h2>统一告警中心</h2>
        <p>当前接入系统日志快照，并尝试订阅 WebSocket 实时消息，统一展示严重告警、预警和通知。</p>
      </div>
      <el-tag :type="connectionTagType" effect="dark">{{ connectionLabel }}</el-tag>
    </div>

    <el-card class="card-shell">
      <div class="toolbar">
        <el-switch v-model="enableSound" active-text="严重告警播放提示音" />
        <el-switch v-model="enableSms" active-text="短信网关预留开关" />
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
          <div class="label">系统通知</div>
          <div class="value">{{ infoCount }}</div>
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
        <el-table-column prop="module" label="模块" min-width="130" />
        <el-table-column prop="message" label="告警内容" min-width="360" show-overflow-tooltip />
        <el-table-column label="通知动作" min-width="220">
          <template #default="{ row }">
            <span>{{ row.level === 'danger' ? notificationText : '仅展示' }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getSystemLogs } from '../api/systemApi'
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
  if (content.includes('warn') || content.includes('warning') || content.includes('超时')) {
    return 'warning'
  }
  return 'info'
}

function parseSystemLogRow(row, currentFarmCode) {
  if (!row) return null

  const timestamp = row.timestamp || row.time || row.operationTime || ''
  const message = typeof row === 'string' ? row : row.message || row.details || JSON.stringify(row)
  const level = typeof row === 'string'
    ? inferLevel(row)
    : inferLevel(row.level || row.message || row.details)

  return {
    id: typeof row === 'object' && row.id ? `system-${row.id}` : `system-${timestamp}-${message}`,
    time: toDisplayTime(timestamp),
    rawTime: timestamp || Date.now(),
    station: row.farm_code || row.station || currentFarmCode || '系统级',
    level,
    module: row.module || row.source || '系统日志',
    message,
    source: 'system-log'
  }
}

function parseRealtimeAlert(payload, currentFarmCode) {
  if (!payload) return null

  const timestamp = payload.timestamp || Date.now()
  return {
    id: `rt-${payload.id || timestamp}`,
    time: toDisplayTime(timestamp),
    rawTime: timestamp,
    station: payload.farm_code || payload.station || currentFarmCode || '当前场站',
    level: payload.level || inferLevel(payload.message || payload.details),
    module: payload.module || payload.source || '实时消息',
    message: payload.message || payload.details || JSON.stringify(payload),
    source: 'websocket'
  }
}

export default {
  name: 'AlarmCenter',
  setup() {
    const enableSound = ref(true)
    const enableSms = ref(false)
    const loading = ref(false)
    const errorMessage = ref('')
    const alerts = ref([])
    const connected = ref(false)

    const dangerCount = computed(() => alerts.value.filter(item => item.level === 'danger').length)
    const warningCount = computed(() => alerts.value.filter(item => item.level === 'warning').length)
    const infoCount = computed(() => alerts.value.filter(item => item.level === 'info').length)

    const connectionLabel = computed(() => (connected.value ? '实时连接已建立' : '仅展示日志快照'))
    const connectionTagType = computed(() => (connected.value ? 'success' : 'info'))
    const notificationText = computed(() => {
      const items = []
      if (enableSound.value) items.push('提示音')
      if (enableSms.value) items.push('短信网关预留')
      return items.length > 0 ? items.join(' + ') : '前端静默'
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
        console.warn('提示音播放失败', error)
      }
    }

    const mergeAlerts = (incoming = []) => {
      const dedupe = new Map()
      ;[...incoming, ...alerts.value].forEach((item) => {
        if (!item) return
        dedupe.set(item.id, item)
      })

      alerts.value = Array.from(dedupe.values())
        .sort((a, b) => String(b.rawTime).localeCompare(String(a.rawTime)))
        .slice(0, 50)
    }

    const loadSystemLogs = async () => {
      loading.value = true
      errorMessage.value = ''
      try {
        const response = await getSystemLogs()
        const rows = Array.isArray(response.data)
          ? response.data
          : Array.isArray(response.data?.logs)
            ? response.data.logs
            : []
        const currentFarmCode = farmService.getCurrentFarm()
        alerts.value = rows
          .map((row) => parseSystemLogRow(row, currentFarmCode))
          .filter(Boolean)
      } catch (error) {
        console.error('加载系统告警失败:', error)
        alerts.value = []
        errorMessage.value = error.response?.data?.error || '加载系统告警失败，页面未获取到日志快照。'
        ElMessage.error(errorMessage.value)
      } finally {
        loading.value = false
      }
    }

    const handleRealtimeAlert = (payload) => {
      const alert = parseRealtimeAlert(payload, farmService.getCurrentFarm())
      if (!alert) return
      mergeAlerts([alert])
      if (alert.level === 'danger') {
        playBeep()
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
        console.warn('告警中心未建立实时连接，将继续展示日志快照', error)
      }
    }

    const refresh = async () => {
      await loadSystemLogs()
      playBeep()
    }

    onMounted(async () => {
      await loadSystemLogs()

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
      loading,
      errorMessage,
      alerts,
      dangerCount,
      warningCount,
      infoCount,
      connectionLabel,
      connectionTagType,
      notificationText,
      levelLabel,
      levelTagType,
      refresh
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

.result-alert {
  margin-bottom: 12px;
}

.stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
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

@media (max-width: 960px) {
  .page-header {
    flex-direction: column;
  }

  .stats {
    grid-template-columns: 1fr;
  }
}
</style>
