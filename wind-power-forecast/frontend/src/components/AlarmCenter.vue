<template>
  <div class="alarm-center page-shell">
    <div class="page-header">
      <div>
        <h2>告警处置</h2>
        <p>集中确认运行异常，查看通知结果，并维护告警规则与通知策略。</p>
      </div>
      <el-tag :type="connectionTagType" effect="dark">{{ connectionLabel }}</el-tag>
    </div>

    <el-card class="card-shell">
      <div class="toolbar">
        <el-switch v-model="enableSound" active-text="声音通知预览" />
        <el-switch v-model="enableSms" active-text="短信记录展示" />
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
          <div class="label">提示</div>
          <div class="value">{{ infoCount }}</div>
        </div>
        <div class="stat neutral">
          <div class="label">通知记录</div>
          <div class="value">{{ visibleNotifications.length }}</div>
        </div>
      </div>

      <el-table :data="alerts" border stripe empty-text="暂无告警" class="alerts-table">
        <el-table-column prop="time" label="告警时间" width="170" />
        <el-table-column prop="station" label="场站" width="110" show-overflow-tooltip />
        <el-table-column label="级别" width="90">
          <template #default="{ row }">
            <el-tag :type="levelTagType(row.level)" effect="dark">{{ levelLabel(row.level) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="告警内容" min-width="320">
          <template #default="{ row }">
            <div class="alarm-message">
              <div class="alarm-message-meta">
                <el-tag size="small" effect="plain">{{ row.module }}</el-tag>
                <span v-if="notificationText(row) !== '无'">通知：{{ notificationText(row) }}</span>
              </div>
              <el-tooltip :content="row.message" placement="top" :show-after="500">
                <span class="alarm-message-text">{{ row.message }}</span>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="128" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link :disabled="row.status !== 'open'" @click="handleAck(row)">确认</el-button>
            <el-button type="danger" link :disabled="row.status === 'closed'" @click="handleClose(row)">关闭</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="notification-panel">
        <div class="panel-title">通知记录</div>
        <el-table :data="visibleNotifications" border size="small" empty-text="暂无通知记录">
          <el-table-column prop="occurredAt" label="时间" min-width="160" />
          <el-table-column prop="channel" label="渠道" width="100" />
          <el-table-column prop="status" label="状态" width="100" />
          <el-table-column prop="message" label="内容" min-width="320" show-overflow-tooltip />
        </el-table>
      </div>
    </el-card>

    <div class="config-grid">
      <el-card class="card-shell">
        <template #header>
          <div class="config-header">
            <span>告警规则</span>
            <el-button type="primary" size="small" @click="openRuleDialog()">新增规则</el-button>
          </div>
        </template>
        <el-table :data="rules" size="small" border empty-text="暂无规则">
          <el-table-column prop="rule_name" label="规则名称" min-width="140" />
          <el-table-column prop="module" label="模块" min-width="100" />
          <el-table-column prop="keyword" label="关键字" min-width="120" />
          <el-table-column label="级别" width="90">
            <template #default="{ row }">
              <el-tag :type="levelTagType(row.level)">{{ levelLabel(row.level) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="启用" width="80">
            <template #default="{ row }">
              <el-switch :model-value="row.is_enabled" @change="toggleRule(row, $event)" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="130">
            <template #default="{ row }">
              <el-button link type="primary" @click="openRuleDialog(row)">编辑</el-button>
              <el-button link type="danger" @click="handleDeleteRule(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card class="card-shell">
        <template #header>
          <div class="config-header">
            <span>通知策略</span>
            <el-button type="primary" size="small" @click="openPolicyDialog()">新增策略</el-button>
          </div>
        </template>
        <el-table :data="policies" size="small" border empty-text="暂无策略">
          <el-table-column prop="policy_name" label="策略名称" min-width="140" />
          <el-table-column prop="channel" label="渠道" width="90" />
          <el-table-column prop="target" label="目标" min-width="140" />
          <el-table-column prop="cooldown_minutes" label="冷却(分钟)" width="110" />
          <el-table-column label="启用" width="80">
            <template #default="{ row }">
              <el-switch :model-value="row.is_enabled" @change="togglePolicy(row, $event)" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="130">
            <template #default="{ row }">
              <el-button link type="primary" @click="openPolicyDialog(row)">编辑</el-button>
              <el-button link type="danger" @click="handleDeletePolicy(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <el-dialog v-model="ruleDialogVisible" :title="ruleForm.id ? '编辑告警规则' : '新增告警规则'" width="560px">
      <el-form :model="ruleForm" label-width="100px">
        <el-form-item label="规则名称"><el-input v-model="ruleForm.rule_name" /></el-form-item>
        <el-form-item label="模块"><el-input v-model="ruleForm.module" /></el-form-item>
        <el-form-item label="关键字"><el-input v-model="ruleForm.keyword" /></el-form-item>
        <el-form-item label="场站编码"><el-input v-model="ruleForm.farm_code" /></el-form-item>
        <el-form-item label="级别">
          <el-select v-model="ruleForm.level">
            <el-option label="严重" value="danger" />
            <el-option label="预警" value="warning" />
            <el-option label="提示" value="info" />
          </el-select>
        </el-form-item>
        <el-form-item label="通知">
          <el-checkbox v-model="ruleForm.notify_sound">声音</el-checkbox>
          <el-checkbox v-model="ruleForm.notify_sms">短信</el-checkbox>
          <el-checkbox v-model="ruleForm.is_enabled">启用</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ruleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="ruleSaving" @click="saveRule">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="policyDialogVisible" :title="policyForm.id ? '编辑通知策略' : '新增通知策略'" width="560px">
      <el-form :model="policyForm" label-width="100px">
        <el-form-item label="策略名称"><el-input v-model="policyForm.policy_name" /></el-form-item>
        <el-form-item label="渠道">
          <el-select v-model="policyForm.channel">
            <el-option label="声音" value="sound" />
            <el-option label="短信" value="sms" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标"><el-input v-model="policyForm.target" /></el-form-item>
        <el-form-item label="最低级别">
          <el-select v-model="policyForm.min_level">
            <el-option label="严重" value="danger" />
            <el-option label="预警" value="warning" />
            <el-option label="提示" value="info" />
          </el-select>
        </el-form-item>
        <el-form-item label="冷却分钟">
          <el-input-number v-model="policyForm.cooldown_minutes" :min="0" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="policyForm.is_enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="policyDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="policySaving" @click="savePolicy">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ackAlarm,
  closeAlarm,
  createAlarmPolicy,
  createAlarmRule,
  deleteAlarmPolicy,
  deleteAlarmRule,
  getAlarmNotifications,
  getAlarmPolicies,
  getAlarmRules,
  getAlarms,
  updateAlarmPolicy,
  updateAlarmRule
} from '../api/systemApi'
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
  if (content.includes('error') || content.includes('failed') || content.includes('exception')) return 'danger'
  if (content.includes('warn') || content.includes('warning')) return 'warning'
  return 'info'
}

function parseBackendAlarm(row, currentFarmCode) {
  if (!row) return null
  return {
    id: row.id,
    time: toDisplayTime(row.occurred_at),
    rawTime: row.occurred_at || Date.now(),
    station: row.farm_code || currentFarmCode || 'SYSTEM',
    level: row.level || 'info',
    status: row.status || 'open',
    module: row.module || row.source || 'alarm-service',
    message: row.message || '',
    source: row.source || 'alarm-service',
    notifySound: Boolean(row.notify_sound),
    notifySms: Boolean(row.notify_sms),
  }
}

function parseRealtimeAlert(payload, currentFarmCode) {
  if (!payload) return null
  const timestamp = payload.timestamp || Date.now()
  return {
    id: `rt-${payload.id || timestamp}`,
    time: toDisplayTime(timestamp),
    rawTime: timestamp,
    station: payload.farm_code || payload.station || currentFarmCode || 'STREAM',
    level: payload.level || inferLevel(payload.message || payload.details),
    status: 'open',
    module: payload.module || payload.source || 'websocket',
    message: payload.message || payload.details || JSON.stringify(payload),
    notifySound: payload.level === 'danger' || inferLevel(payload.message || payload.details) === 'danger',
    notifySms: false,
  }
}

function createEmptyRule() {
  return {
    id: null,
    rule_name: '',
    module: 'system',
    keyword: '',
    farm_code: '',
    level: 'warning',
    is_enabled: true,
    notify_sound: true,
    notify_sms: false
  }
}

function createEmptyPolicy() {
  return {
    id: null,
    policy_name: '',
    channel: 'sound',
    target: '',
    min_level: 'warning',
    cooldown_minutes: 5,
    is_enabled: true
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
    const rules = ref([])
    const policies = ref([])
    const connected = ref(false)
    const ruleDialogVisible = ref(false)
    const policyDialogVisible = ref(false)
    const ruleSaving = ref(false)
    const policySaving = ref(false)
    const ruleForm = reactive(createEmptyRule())
    const policyForm = reactive(createEmptyPolicy())

    const dangerCount = computed(() => alerts.value.filter((item) => item.level === 'danger').length)
    const warningCount = computed(() => alerts.value.filter((item) => item.level === 'warning').length)
    const infoCount = computed(() => alerts.value.filter((item) => item.level === 'info').length)
    const connectionLabel = computed(() => (connected.value ? '实时连接已建立' : '实时连接未建立'))
    const connectionTagType = computed(() => (connected.value ? 'success' : 'info'))
    const visibleNotifications = computed(() => {
      const rows = enableSms.value ? notifications.value : notifications.value.filter((item) => item.channel !== 'sms')
      return rows.slice(0, 20)
    })

    const levelLabel = (level) => (level === 'danger' ? '严重' : level === 'warning' ? '预警' : '提示')
    const levelTagType = (level) => (level === 'danger' ? 'danger' : level === 'warning' ? 'warning' : 'info')
    const statusLabel = (status) => (status === 'acked' ? '已确认' : status === 'closed' ? '已关闭' : '待处理')
    const statusTagType = (status) => (status === 'acked' ? 'warning' : status === 'closed' ? 'info' : 'danger')
    const notificationText = (row) => {
      const items = []
      if (row.notifySound) items.push('声音')
      if (row.notifySms) items.push('短信')
      return items.length > 0 ? items.join(' + ') : '无'
    }

    const resetRuleForm = () => Object.assign(ruleForm, createEmptyRule())
    const resetPolicyForm = () => Object.assign(policyForm, createEmptyPolicy())

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
        console.warn('play beep failed', error)
      }
    }

    const mergeAlerts = (incoming = []) => {
      const dedupe = new Map()
      ;[...incoming, ...alerts.value].forEach((item) => {
        if (item) dedupe.set(String(item.id), item)
      })
      alerts.value = Array.from(dedupe.values())
        .filter((item) => statusFilter.value === 'all' || item.status === statusFilter.value)
        .sort((a, b) => String(b.rawTime).localeCompare(String(a.rawTime)))
        .slice(0, 100)
    }

    const loadNotifications = async () => {
      const response = await getAlarmNotifications()
      const rows = Array.isArray(response.data) ? response.data : []
      notifications.value = rows.map((item) => ({ ...item, occurredAt: toDisplayTime(item.occurred_at) }))
    }

    const loadAlarms = async () => {
      const params = statusFilter.value === 'all' ? {} : { status: statusFilter.value }
      const response = await getAlarms(params)
      const currentFarmCode = farmService.getCurrentFarm()
      const rows = Array.isArray(response.data) ? response.data : []
      alerts.value = rows.map((row) => parseBackendAlarm(row, currentFarmCode)).filter(Boolean)
    }

    const loadConfigs = async () => {
      const [rulesResp, policiesResp] = await Promise.all([getAlarmRules(), getAlarmPolicies()])
      rules.value = Array.isArray(rulesResp.data) ? rulesResp.data : []
      policies.value = Array.isArray(policiesResp.data) ? policiesResp.data : []
    }

    const refresh = async () => {
      loading.value = true
      errorMessage.value = ''
      try {
        await Promise.all([loadAlarms(), loadNotifications(), loadConfigs()])
        playBeep()
      } catch (error) {
        console.warn('refresh alarms failed', error)
      } finally {
        loading.value = false
      }
    }

    const handleRealtimeAlert = async (payload) => {
      const alert = parseRealtimeAlert(payload, farmService.getCurrentFarm())
      if (!alert) return
      mergeAlerts([alert])
      if (alert.level === 'danger') playBeep()
      try {
        await loadNotifications()
      } catch (error) {
        console.warn('refresh notifications failed', error)
      }
    }

    const handleConnected = () => { connected.value = true }
    const handleDisconnected = () => { connected.value = false }

    const connectRealtime = async () => {
      try {
        await websocketService.connect()
        await websocketService.subscribeToCurrentFarm()
        connected.value = true
      } catch (error) {
        connected.value = false
        console.warn('realtime connection failed', error)
      }
    }

    const handleAck = async (row) => {
      try {
        await ackAlarm(row.id)
        ElMessage.success('告警已确认')
        await refresh()
      } catch (error) {
        console.warn('确认告警失败:', error)
      }
    }

    const handleClose = async (row) => {
      try {
        await closeAlarm(row.id)
        ElMessage.success('告警已关闭')
        await refresh()
      } catch (error) {
        console.warn('关闭告警失败:', error)
      }
    }

    const openRuleDialog = (row = null) => {
      resetRuleForm()
      if (row) Object.assign(ruleForm, row)
      ruleDialogVisible.value = true
    }

    const openPolicyDialog = (row = null) => {
      resetPolicyForm()
      if (row) Object.assign(policyForm, row)
      policyDialogVisible.value = true
    }

    const saveRule = async () => {
      ruleSaving.value = true
      try {
        const payload = { ...ruleForm }
        if (payload.id) {
          await updateAlarmRule(payload.id, payload)
        } else {
          await createAlarmRule(payload)
        }
        ruleDialogVisible.value = false
        ElMessage.success('告警规则已保存')
        await loadConfigs()
      } catch (error) {
        console.warn('保存告警规则失败:', error)
      } finally {
        ruleSaving.value = false
      }
    }

    const savePolicy = async () => {
      policySaving.value = true
      try {
        const payload = { ...policyForm }
        if (payload.id) {
          await updateAlarmPolicy(payload.id, payload)
        } else {
          await createAlarmPolicy(payload)
        }
        policyDialogVisible.value = false
        ElMessage.success('通知策略已保存')
        await loadConfigs()
      } catch (error) {
        console.warn('保存通知策略失败:', error)
      } finally {
        policySaving.value = false
      }
    }

    const toggleRule = async (row, value) => {
      try {
        await updateAlarmRule(row.id, { is_enabled: value })
        row.is_enabled = value
      } catch (error) { console.warn('切换规则状态失败:', error) }
    }

    const togglePolicy = async (row, value) => {
      try {
        await updateAlarmPolicy(row.id, { is_enabled: value })
        row.is_enabled = value
      } catch (error) { console.warn('切换策略状态失败:', error) }
    }

    const handleDeleteRule = async (row) => {
      try {
        await ElMessageBox.confirm(`确认删除规则 ${row.rule_name} 吗？`, '提示', { type: 'warning' })
        await deleteAlarmRule(row.id)
        ElMessage.success('告警规则已删除')
        await loadConfigs()
      } catch (error) { if (error !== 'cancel') console.warn('删除规则失败:', error) }
    }

    const handleDeletePolicy = async (row) => {
      try {
        await ElMessageBox.confirm(`确认删除策略 ${row.policy_name} 吗？`, '提示', { type: 'warning' })
        await deleteAlarmPolicy(row.id)
        ElMessage.success('通知策略已删除')
        await loadConfigs()
      } catch (error) { if (error !== 'cancel') console.warn('删除策略失败:', error) }
    }

    onMounted(async () => {
      await refresh()
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
      rules,
      policies,
      visibleNotifications,
      dangerCount,
      warningCount,
      infoCount,
      connectionLabel,
      connectionTagType,
      levelLabel,
      levelTagType,
      statusLabel,
      statusTagType,
      notificationText,
      refresh,
      handleAck,
      handleClose,
      ruleDialogVisible,
      policyDialogVisible,
      ruleForm,
      policyForm,
      ruleSaving,
      policySaving,
      openRuleDialog,
      openPolicyDialog,
      saveRule,
      savePolicy,
      toggleRule,
      togglePolicy,
      handleDeleteRule,
      handleDeletePolicy,
    }
  }
}
</script>

<style scoped>
.alarm-center {
  min-height: 100%;
  padding: 28px 32px 40px;
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
  background: var(--surface);
  border: 1px solid var(--border-color);
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 14px;
  align-items: center;
}

.toolbar-select {
  width: 180px;
}

.result-alert {
  margin-bottom: 12px;
}

.stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.stat {
  min-height: 96px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  border-radius: 12px;
  padding: 16px;
  color: var(--text-primary);
  background: var(--surface);
  border: 1px solid var(--border-color);
  position: relative;
  overflow: hidden;
}

.stat .label {
  font-size: 13px;
  color: var(--text-muted);
}

.stat .value {
  font-size: 30px;
  font-weight: 700;
  margin-top: 4px;
}

.danger { border-top: 3px solid var(--danger); }
.warning { border-top: 3px solid var(--warning); }
.info { border-top: 3px solid var(--accent-blue); }
.neutral { border-top: 3px solid #64736a; }
.danger .value { color: var(--danger); }
.warning .value { color: var(--warning); }
.info .value { color: var(--accent-blue); }
.neutral .value { color: #64736a; }

.notification-panel {
  margin-top: 18px;
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 10px;
}

.alerts-table :deep(.el-table__cell.el-table-fixed-column--right) {
  background: var(--surface) !important;
}

.alarm-message {
  min-width: 0;
}

.alarm-message-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  color: var(--text-secondary);
  font-size: 12px;
}

.alarm-message-text {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.config-grid {
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.config-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

@media (max-width: 960px) {
  .page-header,
  .config-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .stats,
  .config-grid {
    grid-template-columns: 1fr;
  }
}
</style>
