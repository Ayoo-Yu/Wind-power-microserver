<template>
  <div class="scada-connection-page page-shell">
    <div class="gradient-background"></div>

    <div class="page-header">
      <h1 class="page-title">SCADA数据源管理</h1>
      <p class="page-description">配置和管理各场站的SCADA数据源连接，实时监控数据采集状态</p>
    </div>

    <!-- Toolbar -->
    <div class="toolbar">
      <el-button type="primary" @click="openAddDialog" :icon="Plus">新建连接</el-button>
      <el-button @click="loadConnections" :icon="Refresh" :loading="loading">刷新</el-button>
      <el-switch v-model="autoRefresh" active-text="自动刷新" inactive-text="" style="margin-left: 16px" />
    </div>

    <!-- Connection Cards -->
    <div v-loading="loading" class="connection-grid">
      <el-empty v-if="!loading && connections.length === 0" description='暂无SCADA连接配置，点击"新建连接"开始' />

      <div v-for="conn in connections" :key="conn.id" class="connection-card" :class="`status-${healthStatus(conn)}`">
        <div class="card-top">
          <div class="card-status">
            <span class="status-dot" :class="healthStatus(conn)"></span>
            <span class="status-text">{{ healthText(conn) }}</span>
          </div>
          <div class="card-tags">
            <el-tag size="small" :type="conn.status === 'running' ? 'success' : 'info'">
              Worker {{ statusText(conn.status) }}
            </el-tag>
            <el-tag size="small" :type="conn.protocol === 'c104' ? '' : 'warning'">
              {{ conn.protocol === 'c104' ? 'C104' : 'HTTP轮询' }}
            </el-tag>
          </div>
        </div>

        <div class="card-body">
          <h3 class="conn-name">{{ conn.name }}</h3>
          <div class="conn-meta">
            <span class="meta-item">
              <el-icon><OfficeBuilding /></el-icon>
              {{ conn.farm_code }}
            </span>
            <span class="meta-item">
              <el-icon><LinkIcon /></el-icon>
              {{ conn.server_ip }}:{{ conn.server_port }}
            </span>
            <span v-if="conn.upload_target_ioa" class="meta-item">
              <el-icon><DataLine /></el-icon>
              IOA {{ conn.upload_target_ioa }}
            </span>
          </div>

          <div v-if="conn.last_power_value !== null && conn.last_power_value !== undefined" class="power-display">
            <span class="power-value">{{ (conn.last_power_value / 10).toFixed(2) }}</span>
            <span class="power-unit">MW</span>
          </div>
          <div v-else class="power-display power-empty">
            <span class="power-unit">暂无数据</span>
          </div>

          <div v-if="conn.health?.last_data_at || conn.last_data_at" class="last-data">
            最后有效样本: {{ formatTime(conn.health?.last_data_at || conn.last_data_at) }}
          </div>
          <div v-if="conn.health" class="closed-loop-status">
            <span>实际功率: {{ formatTime(conn.health.latest_actual_timestamp) }}</span>
            <span>预测: {{ predictionText(conn.health.prediction?.state) }}</span>
            <span>上报: {{ reportText(conn.health.report?.state) }}</span>
          </div>
          <div v-if="conn.health?.reason || conn.status_message" class="status-msg" :class="{ 'is-error': ['error', 'stale', 'degraded'].includes(healthStatus(conn)) }">
            {{ conn.health?.reason || conn.status_message }}
          </div>
        </div>

        <div class="card-actions">
          <el-button-group>
            <el-button
              v-if="!isWorkerActive(conn)"
              type="success"
              size="small"
              @click="handleStart(conn)"
              :loading="actionLoading[conn.id]"
            >启动</el-button>
            <el-button
              v-if="isWorkerActive(conn)"
              type="warning"
              size="small"
              @click="handleStop(conn)"
              :loading="actionLoading[conn.id]"
            >停止</el-button>
            <el-button
              v-if="isWorkerActive(conn)"
              type="info"
              size="small"
              @click="handleRestart(conn)"
              :loading="actionLoading[conn.id]"
            >重启</el-button>
            <el-button size="small" @click="handleTest(conn)" :loading="actionLoading[conn.id]">测试</el-button>
          </el-button-group>
          <el-button-group>
            <el-button size="small" @click="openEditDialog(conn)" :disabled="isWorkerActive(conn)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(conn)" :disabled="isWorkerActive(conn)">删除</el-button>
          </el-button-group>
        </div>
      </div>
    </div>

    <!-- Add/Edit Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑SCADA连接' : '新建SCADA连接'"
      width="600px"
      destroy-on-close
    >
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="120px">
        <el-form-item label="场站" prop="farm_code">
          <el-select
            v-if="!isEditing"
            v-model="form.farm_code"
            placeholder="选择场站"
            filterable
            style="width: 100%"
          >
            <el-option
              v-for="farm in availableFarms"
              :key="farm.farm_code"
              :label="`${farm.farm_name} (${farm.farm_code})`"
              :value="farm.farm_code"
              :disabled="farm.has_connection"
            />
          </el-select>
          <el-input v-else :model-value="form.farm_code" disabled />
        </el-form-item>

        <el-form-item label="连接名称" prop="name">
          <el-input v-model="form.name" placeholder="如：仓房SCADA" />
        </el-form-item>

        <el-form-item label="连接协议" prop="protocol">
          <el-radio-group v-model="form.protocol">
            <el-radio value="c104">IEC 60870-5-104（生产）</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="服务器地址" prop="server_ip">
          <el-input v-model="form.server_ip" placeholder="192.168.1.100" />
        </el-form-item>

        <el-form-item label="端口" prop="server_port">
          <el-input-number v-model="form.server_port" :min="1" :max="65535" />
        </el-form-item>

        <el-form-item label="CASDU地址" prop="casdu_address" v-if="form.protocol === 'c104'">
          <el-input-number v-model="form.casdu_address" :min="0" :max="65535" />
        </el-form-item>

        <el-form-item label="功率IOA地址" prop="upload_target_ioa" v-if="form.protocol === 'c104'">
          <el-input-number v-model="form.upload_target_ioa" :min="0" :max="65535" placeholder="如16385" />
          <div class="form-hint">SCADA服务器上该场站实时功率对应的IOA地址（管理员提供）</div>
        </el-form-item>

        <el-form-item label="采集间隔(秒)" prop="fetch_interval">
          <el-input-number v-model="form.fetch_interval" :min="10" :max="3600" :step="10" />
        </el-form-item>

        <el-form-item label="IOA点位" prop="ioa_points" v-if="form.protocol === 'c104'">
          <div class="ioa-points-editor">
            <div v-for="(type, ioa) in form.ioa_points" :key="ioa" class="ioa-row">
              <el-input :model-value="ioa" @update:model-value="val => updateIoaAddress(ioa, val)" style="width: 120px" />
              <el-select :model-value="type" @update:model-value="val => updateIoaType(ioa, val)" style="width: 180px">
                <el-option label="M_ME_NC_1 (短浮点)" value="M_ME_NC_1" />
                <el-option label="M_ME_NB_1 (标度化)" value="M_ME_NB_1" />
                <el-option label="M_SP_TB_1 (带时标单点)" value="M_SP_TB_1" />
              </el-select>
              <el-button type="danger" :icon="Delete" circle size="small" @click="removeIoa(ioa)" />
            </div>
            <div class="ioa-add-row">
              <el-input v-model="newIoa.ioa" placeholder="IOA地址" style="width: 120px" />
              <el-select v-model="newIoa.type" style="width: 180px">
                <el-option label="M_ME_NC_1" value="M_ME_NC_1" />
                <el-option label="M_ME_NB_1" value="M_ME_NB_1" />
                <el-option label="M_SP_TB_1" value="M_SP_TB_1" />
              </el-select>
              <el-button type="primary" :icon="Plus" circle size="small" @click="addIoa" />
            </div>
          </div>
        </el-form-item>

        <el-form-item label="启用">
          <el-switch v-model="form.is_enabled" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, reactive, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus, Refresh, Delete, OfficeBuilding, Link as LinkIcon, DataLine
} from '@element-plus/icons-vue'
import * as scadaApi from '../api/scadaApi'

export default {
  name: 'ScadaConnection',
  components: { OfficeBuilding, LinkIcon, DataLine },
  setup() {
    const connections = ref([])
    const availableFarms = ref([])
    const loading = ref(false)
    const autoRefresh = ref(true)
    const actionLoading = reactive({})
    const dialogVisible = ref(false)
    const isEditing = ref(false)
    const editingId = ref(null)
    const saving = ref(false)
    const formRef = ref(null)

    const form = reactive({
      farm_code: '',
      name: '',
      protocol: 'c104',
      server_ip: '',
      server_port: 2404,
      casdu_address: 1,
      upload_target_ioa: null,
      fetch_interval: 60,
      ioa_points: {},
      is_enabled: true,
    })

    const newIoa = reactive({ ioa: '', type: 'M_ME_NC_1' })

    const formRules = {
      farm_code: [{ required: true, message: '请选择场站', trigger: 'change' }],
      name: [{ required: true, message: '请输入连接名称', trigger: 'blur' }],
      server_ip: [{ required: true, message: '请输入服务器地址', trigger: 'blur' }],
      server_port: [{ required: true, message: '请输入端口', trigger: 'blur' }],
    }

    let refreshTimer = null

    const statusText = (status) => {
      const map = { stopped: '已停止', running: '运行中', error: '异常', connecting: '连接中' }
      return map[status] || status
    }

    const healthStatus = (conn) => conn.health?.status || conn.status || 'unknown'
    const isWorkerActive = (conn) => ['running', 'connecting', 'stopping', 'restart_requested'].includes(conn.status)

    const healthText = (conn) => {
      const map = {
        healthy: '采集健康', degraded: '质量降级', stale: '数据陈旧',
        no_data: '等待数据', connecting: '连接中', error: '采集异常',
        stopped: '已停止', disabled: '已停用', deployment_disabled: '部署未启用',
        unknown: '状态未知'
      }
      return map[healthStatus(conn)] || healthStatus(conn)
    }

    const predictionText = (state) => {
      const map = {
        current: '已消费最新数据', pending: '等待下一轮', running: '运行中',
        failed: '最近执行失败', not_configured: '未配置', unknown: '未知'
      }
      return map[state] || state || '--'
    }

    const reportText = (state) => {
      const map = {
        sent: '最近发送成功', pending: '队列处理中', failed: '最近发送失败',
        idle: '等待任务', not_configured: '未配置', unknown: '未知'
      }
      return map[state] || state || '--'
    }

    const formatTime = (iso) => {
      if (!iso) return '--'
      const d = new Date(iso)
      return d.toLocaleString('zh-CN', { hour12: false })
    }

    const loadConnections = async () => {
      loading.value = true
      try {
        connections.value = await scadaApi.listConnections()
      } catch (e) {
        console.error('Failed to load connections:', e)
      } finally {
        loading.value = false
      }
    }

    const loadAvailableFarms = async () => {
      try {
        availableFarms.value = await scadaApi.getAvailableFarms()
      } catch (e) {
        console.error('Failed to load farms:', e)
      }
    }

    const openAddDialog = () => {
      isEditing.value = false
      editingId.value = null
      Object.assign(form, {
        farm_code: '', name: '', protocol: 'c104',
        server_ip: '', server_port: 2404, casdu_address: 1,
        upload_target_ioa: null, fetch_interval: 60, ioa_points: {}, is_enabled: true,
      })
      newIoa.ioa = ''
      newIoa.type = 'M_ME_NC_1'
      dialogVisible.value = true
      loadAvailableFarms()
    }

    const openEditDialog = (conn) => {
      isEditing.value = true
      editingId.value = conn.id
      Object.assign(form, {
        farm_code: conn.farm_code,
        name: conn.name,
        protocol: conn.protocol || 'c104',
        server_ip: conn.server_ip,
        server_port: conn.server_port,
        casdu_address: conn.casdu_address,
        upload_target_ioa: conn.upload_target_ioa,
        fetch_interval: conn.fetch_interval,
        ioa_points: { ...(conn.ioa_points || {}) },
        is_enabled: conn.is_enabled,
      })
      newIoa.ioa = ''
      newIoa.type = 'M_ME_NC_1'
      dialogVisible.value = true
    }

    const handleSave = async () => {
      if (!formRef.value) return
      try {
        await formRef.value.validate()
      } catch { return }

      saving.value = true
      try {
        const payload = { ...form }
        if (isEditing.value) {
          await scadaApi.updateConnection(editingId.value, payload)
          ElMessage.success('连接已更新')
        } else {
          await scadaApi.createConnection(payload)
          ElMessage.success('连接已创建')
        }
        dialogVisible.value = false
        loadConnections()
      } catch (e) {
        ElMessage.error(e.response?.data?.error || '保存失败')
      } finally {
        saving.value = false
      }
    }

    const handleStart = async (conn) => {
      actionLoading[conn.id] = true
      try {
        await scadaApi.startConnection(conn.id)
        ElMessage.success(`${conn.name} 正在启动`)
        setTimeout(loadConnections, 1500)
      } catch (e) {
        ElMessage.error(e.response?.data?.error || '启动失败')
      } finally {
        actionLoading[conn.id] = false
      }
    }

    const handleStop = async (conn) => {
      actionLoading[conn.id] = true
      try {
        await scadaApi.stopConnection(conn.id)
        ElMessage.success(`${conn.name} 已停止`)
        loadConnections()
      } catch (e) {
        ElMessage.error(e.response?.data?.error || '停止失败')
      } finally {
        actionLoading[conn.id] = false
      }
    }

    const handleRestart = async (conn) => {
      actionLoading[conn.id] = true
      try {
        await scadaApi.restartConnection(conn.id)
        ElMessage.success(`${conn.name} 正在重启`)
        setTimeout(loadConnections, 2000)
      } catch (e) {
        ElMessage.error(e.response?.data?.error || '重启失败')
      } finally {
        actionLoading[conn.id] = false
      }
    }

    const handleTest = async (conn) => {
      actionLoading[conn.id] = true
      try {
        const result = await scadaApi.testConnection(conn.id)
        if (result.success) {
          ElMessage.success(`连接测试成功: ${conn.server_ip}:${conn.server_port}`)
        } else {
          ElMessage.error(result.error || '连接测试失败')
        }
      } catch (e) {
        ElMessage.error(e.response?.data?.error || '连接测试失败')
      } finally {
        actionLoading[conn.id] = false
      }
    }

    const handleDelete = async (conn) => {
      try {
        await ElMessageBox.confirm(
          `确定删除"${conn.name}"的SCADA连接配置？此操作不可恢复。`,
          '确认删除',
          { type: 'warning' }
        )
        await scadaApi.deleteConnection(conn.id)
        ElMessage.success('连接已删除')
        loadConnections()
      } catch (error) {
        if (error !== 'cancel' && error !== 'close') {
          ElMessage.error(error.response?.data?.error || '删除连接失败')
        }
      }
    }

    const addIoa = () => {
      if (!newIoa.ioa) return
      form.ioa_points = { ...form.ioa_points, [newIoa.ioa]: newIoa.type }
      newIoa.ioa = ''
    }

    const removeIoa = (ioa) => {
      const updated = { ...form.ioa_points }
      delete updated[ioa]
      form.ioa_points = updated
    }

    const updateIoaType = (ioa, val) => {
      form.ioa_points = { ...form.ioa_points, [ioa]: val }
    }

    const updateIoaAddress = (oldIoa, newIoa) => {
      if (!newIoa || newIoa === oldIoa) return
      const updated = {}
      for (const [k, v] of Object.entries(form.ioa_points)) {
        updated[k === oldIoa ? String(newIoa) : k] = v
      }
      form.ioa_points = updated
    }

    const startRefreshTimer = () => {
      if (refreshTimer) clearInterval(refreshTimer)
      refreshTimer = setInterval(loadConnections, 15000)
    }
    const stopRefreshTimer = () => {
      if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null }
    }

    watch(autoRefresh, (enabled) => {
      if (enabled) startRefreshTimer()
      else stopRefreshTimer()
    })

    onMounted(() => {
      loadConnections()
      if (autoRefresh.value) startRefreshTimer()
    })

    onUnmounted(() => {
      stopRefreshTimer()
    })

    return {
      connections, availableFarms, loading, autoRefresh,
      actionLoading, dialogVisible, isEditing, saving,
      formRef, form, formRules, newIoa,
      statusText, healthStatus, isWorkerActive, healthText, predictionText, reportText,
      formatTime, loadConnections,
      openAddDialog, openEditDialog, handleSave,
      handleStart, handleStop, handleRestart, handleTest, handleDelete,
      addIoa, removeIoa, updateIoaType, updateIoaAddress,
      Plus, Refresh, Delete,
    }
  }
}
</script>

<style scoped>
.scada-connection-page {
  position: relative;
  min-height: 100vh;
  padding: 20px;
}
.gradient-background {
  position: fixed;
  inset: 0;
  z-index: -1;
  background: linear-gradient(135deg, #0c1b2e 0%, #0f2744 50%, #0a1a2f 100%);
}
.page-header {
  text-align: center;
  margin-bottom: 20px;
}
.page-title {
  margin: 0 0 6px;
  color: var(--text-primary, #e0e8f0);
  font-size: 22px;
}
.page-description {
  margin: 0;
  color: var(--text-secondary, #8ba4bf);
  font-size: 14px;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

/* Connection Grid */
.connection-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 16px;
}

/* Connection Card */
.connection-card {
  border: 1px solid rgba(146, 186, 220, 0.2);
  border-radius: 12px;
  background: rgba(8, 24, 38, 0.65);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: border-color 0.3s, box-shadow 0.3s;
}
.connection-card:hover {
  border-color: rgba(64, 158, 255, 0.4);
  box-shadow: 0 4px 20px rgba(64, 158, 255, 0.08);
}
.connection-card.status-running {
  border-left: 3px solid #67c23a;
}
.connection-card.status-healthy {
  border-left: 3px solid #67c23a;
}
.connection-card.status-degraded,
.connection-card.status-stale,
.connection-card.status-no_data,
.connection-card.status-connecting {
  border-left: 3px solid #e6a23c;
}
.connection-card.status-error {
  border-left: 3px solid #f56c6c;
}
.connection-card.status-stopped,
.connection-card.status-disabled,
.connection-card.status-deployment_disabled,
.connection-card.status-unknown {
  border-left: 3px solid #909399;
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-status {
  display: flex;
  align-items: center;
  gap: 6px;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.status-dot.running { background: #67c23a; box-shadow: 0 0 6px rgba(103, 194, 58, 0.6); }
.status-dot.healthy { background: #67c23a; box-shadow: 0 0 6px rgba(103, 194, 58, 0.6); }
.status-dot.degraded,
.status-dot.stale,
.status-dot.no_data { background: #e6a23c; box-shadow: 0 0 6px rgba(230, 162, 60, 0.55); }
.status-dot.stopped { background: #909399; }
.status-dot.disabled,
.status-dot.deployment_disabled,
.status-dot.unknown { background: #909399; }
.status-dot.error { background: #f56c6c; box-shadow: 0 0 6px rgba(245, 108, 108, 0.6); }
.status-dot.connecting { background: #e6a23c; animation: pulse 1.5s infinite; }
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.status-text {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #e0e8f0);
}
.card-tags {
  display: flex;
  align-items: center;
  gap: 6px;
}

.card-body {
  flex: 1;
}
.conn-name {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary, #e0e8f0);
}
.conn-meta {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--text-secondary, #8ba4bf);
}

.power-display {
  display: flex;
  align-items: baseline;
  gap: 4px;
  padding: 8px 12px;
  background: rgba(103, 194, 58, 0.08);
  border-radius: 8px;
  margin-bottom: 8px;
}
.power-display.power-empty {
  background: rgba(144, 147, 153, 0.08);
}
.power-value {
  font-size: 28px;
  font-weight: 700;
  color: #67c23a;
  font-family: 'Consolas', 'Roboto Mono', monospace;
}
.power-empty .power-value {
  color: #909399;
}
.power-unit {
  font-size: 13px;
  color: var(--text-secondary, #8ba4bf);
}

.last-data {
  font-size: 12px;
  color: var(--text-secondary, #8ba4bf);
  font-family: 'Consolas', 'Roboto Mono', monospace;
}
.closed-loop-status {
  display: grid;
  grid-template-columns: 1fr;
  gap: 3px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-secondary, #8ba4bf);
}
.status-msg {
  font-size: 12px;
  color: var(--text-secondary, #8ba4bf);
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.status-msg.is-error {
  color: #f56c6c;
}

.card-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

/* IOA Points Editor */
.ioa-points-editor {
  width: 100%;
}
.ioa-row, .ioa-add-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.form-hint {
  font-size: 12px;
  color: var(--text-secondary, #8ba4bf);
  margin-top: 4px;
  line-height: 1.4;
}

/* Responsive */
@media (max-width: 768px) {
  .connection-grid {
    grid-template-columns: 1fr;
  }
}
</style>
