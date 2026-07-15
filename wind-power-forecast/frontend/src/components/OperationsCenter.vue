<template>
  <div class="operations-center" v-loading="loading">
    <header class="ops-header">
      <div>
        <div class="eyebrow"><el-icon><Monitor /></el-icon><span>FIELD OPERATIONS</span></div>
        <h1>运行控制中心</h1>
        <p>统一查看实时数据、新能源天气、预测链路、上报队列和模型版本。</p>
      </div>
      <div class="header-actions">
        <div :class="['overall-pill', overallState]">
          <span class="state-dot"></span>
          <strong>{{ overallLabel }}</strong>
          <span>{{ issueCount }} 项关注</span>
        </div>
        <el-button :icon="Refresh" type="primary" :loading="loading" @click="loadOverview">
          刷新状态
        </el-button>
      </div>
    </header>

    <section v-if="issues.length" class="issue-strip">
      <div v-for="issue in issues" :key="`${issue.domain}-${issue.message}`" :class="issue.severity">
        <el-icon><WarningFilled /></el-icon>
        <span>{{ issue.message }}</span>
      </div>
    </section>

    <section class="signal-grid">
      <article v-for="signal in signals" :key="signal.key" :class="['signal-card', signal.state]">
        <div class="signal-top">
          <span>{{ signal.label }}</span>
          <el-tag :type="stateTag(signal.state)" effect="dark" round>{{ stateLabel(signal.state) }}</el-tag>
        </div>
        <strong>{{ signal.value }}</strong>
        <small>{{ signal.detail }}</small>
      </article>
    </section>

    <section class="workspace-grid">
      <el-card class="ops-card scada-card" shadow="never">
        <template #header>
          <div class="card-title-row">
            <div>
              <span class="card-title">SCADA 五指标实时链路</span>
              <small>每个场站均按统一点表契约检查新鲜度、质量和单位</small>
            </div>
            <span class="mono">{{ overview?.scada?.stale_after_seconds || 0 }} s 阈值</span>
          </div>
        </template>

        <div v-if="scadaConnections.length" class="connection-list">
          <article v-for="connection in scadaConnections" :key="connection.id" class="connection-block">
            <div class="connection-head">
              <div>
                <strong>{{ connection.name }}</strong>
                <span class="mono">{{ connection.farm_code }}</span>
              </div>
              <div>
                <el-tag size="small" effect="plain">{{ connection.protocol?.toUpperCase() }}</el-tag>
                <el-tag size="small" :type="workerTag(connection.worker_status)">
                  {{ workerLabel(connection.worker_status) }}
                </el-tag>
                <span class="catalog-version mono">{{ connection.point_catalog_version }}</span>
              </div>
            </div>
            <div class="metric-grid">
              <div v-for="metric in connection.metrics" :key="metric.metric" :class="['metric-cell', metric.state]">
                <span>{{ metric.label }}</span>
                <strong>{{ formatMetric(metric) }}</strong>
                <small>{{ freshnessText(metric) }}</small>
              </div>
            </div>
          </article>
        </div>
        <el-empty v-else description="当前没有已配置的 SCADA 场站" :image-size="72" />
      </el-card>

      <el-card class="ops-card nwp-card" shadow="never">
        <template #header>
          <div class="card-title-row">
            <div>
              <span class="card-title">NWP 接入批次</span>
              <small>展示最近完成批次及业务入库质量</small>
            </div>
            <el-tag :type="stateTag(overview?.nwp?.state)" effect="dark" round>
              {{ stateLabel(overview?.nwp?.state) }}
            </el-tag>
          </div>
        </template>
        <el-table :data="nwpBatches" size="small" empty-text="暂无 NWP 接入批次">
          <el-table-column prop="farm_code" label="场站" width="95" />
          <el-table-column label="批次时间" min-width="150">
            <template #default="{ row }">{{ formatDateTime(row.event_time) }}</template>
          </el-table-column>
          <el-table-column label="入库" width="90" align="right">
            <template #default="{ row }">{{ row.accepted_count }}</template>
          </el-table-column>
          <el-table-column label="质量" width="90">
            <template #default="{ row }">
              <el-tag size="small" :type="row.quality_status === 'good' ? 'success' : 'warning'">
                {{ row.quality_status === 'good' ? '正常' : '降级' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="新鲜度" width="100">
            <template #default="{ row }">{{ ageText(row.age_seconds) }}</template>
          </el-table-column>
        </el-table>
      </el-card>
    </section>

    <section class="detail-grid">
      <el-card class="ops-card" shadow="never">
        <template #header>
          <div class="card-title-row">
            <div>
              <span class="card-title">预测输入追溯</span>
              <small>每次预测冻结 SCADA、NWP、模型和数据集版本</small>
            </div>
            <span>{{ inputSnapshots.length }} 条最新快照</span>
          </div>
        </template>
        <el-table :data="inputSnapshots" size="small" empty-text="暂无预测输入快照">
          <el-table-column prop="farm_code" label="场站" width="90" />
          <el-table-column prop="task_type" label="尺度" width="95">
            <template #default="{ row }">{{ taskLabel(row.task_type) }}</template>
          </el-table-column>
          <el-table-column label="捕获时间" min-width="150">
            <template #default="{ row }">{{ formatDateTime(row.captured_at) }}</template>
          </el-table-column>
          <el-table-column label="完整率" width="90" align="right">
            <template #default="{ row }">{{ formatPercent(1 - Number(row.missing_rate || 0)) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag size="small" :type="snapshotTag(row.status)">{{ snapshotLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="数据版本" min-width="150">
            <template #default="{ row }"><span class="mono digest">{{ shortDigest(row.dataset_version) }}</span></template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card class="ops-card" shadow="never">
        <template #header>
          <div class="card-title-row">
            <div>
              <span class="card-title">可靠上报队列</span>
              <small>待发送、重试和死信均由持久化发件箱管理</small>
            </div>
            <div class="queue-summary">
              <span>待处理 <strong>{{ overview?.reporting?.pending_count || 0 }}</strong></span>
              <span>死信 <strong class="danger-text">{{ overview?.reporting?.dead_count || 0 }}</strong></span>
            </div>
          </div>
        </template>
        <el-table :data="reportFailures" size="small" empty-text="当前没有失败或重试任务">
          <el-table-column prop="farm_code" label="场站" width="90" />
          <el-table-column prop="report_type" label="类型" width="100" />
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-tag size="small" :type="row.status === 'dead' ? 'danger' : 'warning'">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="attempt_count" label="尝试" width="70" align="right" />
          <el-table-column prop="last_error" label="最近错误" min-width="180" show-overflow-tooltip />
        </el-table>
      </el-card>
    </section>

    <el-card class="ops-card model-card" shadow="never">
      <template #header>
        <div class="card-title-row">
          <div>
            <span class="card-title">模型版本治理</span>
            <small>现场模式下，新模型需要人工审批，已审批版本支持一键回滚</small>
          </div>
          <div class="model-summary">
            <span>运行中 <strong>{{ overview?.models?.active_count || 0 }}</strong></span>
            <span>待审批 <strong>{{ modelCandidateCount }}</strong></span>
          </div>
        </div>
      </template>
      <el-table :data="modelVersions" size="small" empty-text="暂无已注册模型版本">
        <el-table-column prop="farm_code" label="场站" width="95" />
        <el-table-column label="预测尺度" width="105">
          <template #default="{ row }">{{ taskLabel(row.task_type) }}</template>
        </el-table-column>
        <el-table-column prop="algorithm" label="算法" min-width="120" />
        <el-table-column label="验证准确率" width="115" align="right">
          <template #default="{ row }">{{ formatPercent(row.val_accuracy) }}</template>
        </el-table-column>
        <el-table-column label="生命周期" width="105">
          <template #default="{ row }">
            <el-tag size="small" :type="modelTag(row)">{{ modelStateLabel(row) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="训练时间" min-width="155">
          <template #default="{ row }">{{ formatDateTime(row.trained_at) }}</template>
        </el-table-column>
        <el-table-column label="制品摘要" min-width="130">
          <template #default="{ row }"><span class="mono digest">{{ shortDigest(row.artifact_sha256) }}</span></template>
        </el-table-column>
        <el-table-column v-if="canManageModels" label="治理操作" width="215" fixed="right">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button v-if="row.lifecycle_status === 'candidate'" size="small" type="success" text @click="approve(row)">审批</el-button>
              <el-button v-if="row.lifecycle_status === 'candidate'" size="small" type="danger" text @click="reject(row)">拒绝</el-button>
              <el-button v-if="row.lifecycle_status === 'approved' && !row.is_active" size="small" type="warning" text @click="rollback(row)">回滚至此版本</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <footer class="ops-footer">
      <span>当前场站：{{ currentFarm || '全部场站' }}</span>
      <span>生成时间：{{ formatDateTime(overview?.generated_at) }}</span>
      <span>磁盘：{{ formatBytes(overview?.storage?.free_bytes) }} 可用</span>
    </footer>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Monitor, Refresh, WarningFilled } from '@element-plus/icons-vue'
import {
  approveModelVersion,
  getOperationsOverview,
  rejectModelVersion,
  rollbackModelVersion
} from '../api/operationsApi'
import farmService from '../utils/farmService'
import { getStoredUser, hasPermission } from '../utils/permission'

const loading = ref(false)
const overview = ref(null)
const currentFarm = ref(farmService.getCurrentFarm())
let refreshTimer = null

const canManageModels = computed(() => hasPermission(getStoredUser(), 'manage_tasks'))
const overallState = computed(() => overview.value?.overall?.state || 'unknown')
const issues = computed(() => overview.value?.overall?.issues || [])
const issueCount = computed(() => overview.value?.overall?.issue_count || 0)
const scadaConnections = computed(() => overview.value?.scada?.connections || [])
const nwpBatches = computed(() => overview.value?.nwp?.latest_batches || [])
const inputSnapshots = computed(() => overview.value?.prediction?.latest_input_snapshots || [])
const reportFailures = computed(() => overview.value?.reporting?.latest_failures || [])
const modelVersions = computed(() => overview.value?.models?.recent_versions || [])
const modelCandidateCount = computed(() => overview.value?.models?.lifecycle_counts?.candidate || 0)

const overallLabel = computed(() => ({
  healthy: '运行正常',
  degraded: '运行降级',
  critical: '需要处理'
})[overallState.value] || '状态未知')

const signals = computed(() => {
  const data = overview.value || {}
  const predictionCounts = data.prediction?.status_counts || {}
  const failed = (predictionCounts.failed || 0) + (predictionCounts.failure || 0) + (predictionCounts.error || 0)
  const storageState = Number(data.storage?.used_percent || 0) >= 90
    ? 'critical'
    : (Number(data.storage?.used_percent || 0) >= 80 ? 'degraded' : 'healthy')
  return [
    {
      key: 'scada',
      label: 'SCADA 实时输入',
      state: normalizeSignalState(data.scada?.state),
      value: `${data.scada?.enabled_connection_count || 0} 个场站`,
      detail: `${data.scada?.missing_metric_count || 0} 项缺失，${data.scada?.stale_metric_count || 0} 项过期`
    },
    {
      key: 'nwp',
      label: 'NWP 批次',
      state: normalizeSignalState(data.nwp?.state),
      value: `${data.nwp?.latest_batches?.length || 0} 个场站`,
      detail: `${data.nwp?.stale_farm_count || 0} 个场站数据过期`
    },
    {
      key: 'prediction',
      label: '24 小时预测任务',
      state: failed ? 'degraded' : 'healthy',
      value: `${Object.values(predictionCounts).reduce((sum, value) => sum + Number(value || 0), 0)} 次`,
      detail: failed ? `${failed} 次失败` : '未发现执行失败'
    },
    {
      key: 'reporting',
      label: '可靠上报',
      state: data.reporting?.dead_count ? 'critical' : ((data.reporting?.pending_count || 0) > 0 ? 'degraded' : 'healthy'),
      value: `${data.reporting?.pending_count || 0} 条待处理`,
      detail: `${data.reporting?.dead_count || 0} 条死信`
    },
    {
      key: 'storage',
      label: '运行磁盘',
      state: storageState,
      value: `${Number(data.storage?.used_percent || 0).toFixed(1)}%`,
      detail: `${formatBytes(data.storage?.free_bytes)} 可用`
    }
  ]
})

function normalizeSignalState(state) {
  if (state === 'healthy' || state === 'fresh') return 'healthy'
  if (state === 'missing' || state === 'critical') return 'critical'
  if (state === 'disabled') return 'disabled'
  return 'degraded'
}

function stateLabel(state) {
  return ({
    healthy: '正常', fresh: '新鲜', degraded: '降级', stale: '已过期',
    missing: '缺失', critical: '严重', disabled: '未启用', unknown: '未知'
  })[state] || '需关注'
}

function stateTag(state) {
  const normalized = normalizeSignalState(state)
  return ({ healthy: 'success', degraded: 'warning', critical: 'danger', disabled: 'info' })[normalized] || 'info'
}

function workerTag(status) {
  return ['running', 'connected'].includes(status) ? 'success' : (status === 'error' ? 'danger' : 'warning')
}

function workerLabel(status) {
  return ({ running: '运行中', connected: '已连接', connecting: '连接中', stopped: '已停止', error: '异常' })[status] || status || '未知'
}

function formatMetric(metric) {
  if (metric.value === null || metric.value === undefined) return '暂无数据'
  const digits = metric.metric === 'availability_pct' ? 1 : 2
  return `${Number(metric.value).toFixed(digits)} ${metric.unit}`
}

function ageText(seconds) {
  if (seconds === null || seconds === undefined) return '暂无数据'
  if (seconds < 60) return `${seconds} 秒前`
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟前`
  return `${Math.floor(seconds / 3600)} 小时前`
}

function freshnessText(metric) {
  if (metric.state === 'disabled') return '连接未启用'
  return `${stateLabel(metric.state)} · ${ageText(metric.age_seconds)}`
}

function formatDateTime(value) {
  if (!value) return '暂无'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('zh-CN', { hour12: false })
}

function formatPercent(value) {
  const number = Number(value)
  return Number.isFinite(number) ? `${(number * 100).toFixed(1)}%` : '暂无'
}

function formatBytes(value) {
  const bytes = Number(value)
  if (!Number.isFinite(bytes) || bytes < 0) return '暂无'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = bytes
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  return `${size.toFixed(index > 1 ? 1 : 0)} ${units[index]}`
}

function shortDigest(value) {
  if (!value) return '未记录'
  return `${String(value).slice(0, 12)}…`
}

function taskLabel(value) {
  return ({ supershort: '超短期', short: '短期', medium: '中期' })[value] || value || '未知'
}

function snapshotTag(status) {
  return ({ ready: 'success', degraded: 'warning', blocked: 'danger' })[status] || 'info'
}

function snapshotLabel(status) {
  return ({ ready: '就绪', degraded: '降级', blocked: '阻断' })[status] || status || '未知'
}

function modelTag(row) {
  if (row.is_active) return 'success'
  return ({ candidate: 'warning', approved: 'info', rejected: 'danger' })[row.lifecycle_status] || 'info'
}

function modelStateLabel(row) {
  if (row.is_active) return '运行中'
  return ({ candidate: '待审批', approved: '已审批', rejected: '已拒绝' })[row.lifecycle_status] || '未知'
}

async function loadOverview() {
  loading.value = true
  try {
    const response = await getOperationsOverview(currentFarm.value)
    overview.value = response.data
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '运行状态加载失败')
  } finally {
    loading.value = false
  }
}

async function approve(row) {
  try {
    await ElMessageBox.confirm(
      `确认审批 ${row.farm_code} 的 ${taskLabel(row.task_type)}模型版本 ${row.id}？`,
      '模型审批',
      { type: 'warning', confirmButtonText: '确认审批', cancelButtonText: '取消' }
    )
    await approveModelVersion(row.id)
    ElMessage.success('模型审批完成')
    await loadOverview()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error.response?.data?.message || '模型审批失败')
    }
  }
}

async function reject(row) {
  try {
    const result = await ElMessageBox.prompt('请输入拒绝原因，该原因会写入模型治理记录。', '拒绝模型', {
      inputPattern: /\S+/,
      inputErrorMessage: '拒绝原因不能为空',
      confirmButtonText: '确认拒绝',
      cancelButtonText: '取消'
    })
    await rejectModelVersion(row.id, result.value.trim())
    ElMessage.success('候选模型已拒绝')
    await loadOverview()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error.response?.data?.message || '拒绝模型失败')
    }
  }
}

async function rollback(row) {
  try {
    await ElMessageBox.confirm(
      `确认将 ${row.farm_code} 的 ${taskLabel(row.task_type)}运行版本回滚到 ${row.id}？`,
      '模型回滚',
      { type: 'warning', confirmButtonText: '确认回滚', cancelButtonText: '取消' }
    )
    await rollbackModelVersion(row.id)
    ElMessage.success('模型回滚完成')
    await loadOverview()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error.response?.data?.message || '模型回滚失败')
    }
  }
}

function handleFarmChanged(farmCode) {
  currentFarm.value = farmCode
  loadOverview()
}

onMounted(() => {
  farmService.addListener(handleFarmChanged)
  loadOverview()
  refreshTimer = window.setInterval(loadOverview, 30000)
})

onBeforeUnmount(() => {
  farmService.removeListener(handleFarmChanged)
  if (refreshTimer) window.clearInterval(refreshTimer)
})
</script>

<style scoped>
.operations-center {
  min-height: 100%;
  padding: 24px;
  color: var(--text-primary);
  background:
    radial-gradient(circle at 12% 0%, rgba(18, 215, 255, 0.08), transparent 30%),
    linear-gradient(180deg, rgba(5, 18, 31, 0.8), rgba(5, 18, 31, 0.35));
}

.ops-header,
.card-title-row,
.connection-head,
.signal-top,
.ops-footer,
.header-actions,
.queue-summary,
.model-summary,
.table-actions {
  display: flex;
  align-items: center;
}

.ops-header {
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 18px;
}

.ops-header h1 {
  margin: 5px 0 4px;
  font-size: 30px;
  letter-spacing: 0.02em;
}

.ops-header p,
.card-title-row small {
  margin: 0;
  color: var(--text-secondary);
}

.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--accent);
  font-size: 12px;
  letter-spacing: 0.16em;
}

.header-actions {
  gap: 12px;
}

.overall-pill {
  display: grid;
  grid-template-columns: auto auto;
  align-items: center;
  column-gap: 8px;
  padding: 8px 14px;
  border: 1px solid rgba(146, 186, 220, 0.25);
  border-radius: 12px;
  background: rgba(10, 28, 44, 0.8);
}

.overall-pill > span:last-child {
  grid-column: 2;
  color: var(--text-secondary);
  font-size: 11px;
}

.state-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #7f8d9c;
}

.overall-pill.healthy .state-dot { background: #2dd36f; box-shadow: 0 0 12px rgba(45, 211, 111, 0.7); }
.overall-pill.degraded .state-dot { background: #f6b73c; box-shadow: 0 0 12px rgba(246, 183, 60, 0.6); }
.overall-pill.critical .state-dot { background: #ff5c72; box-shadow: 0 0 12px rgba(255, 92, 114, 0.7); }

.issue-strip {
  display: grid;
  gap: 8px;
  margin-bottom: 16px;
}

.issue-strip > div {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 10px 13px;
  border-radius: 8px;
  font-size: 13px;
}

.issue-strip .warning { color: #ffd47a; background: rgba(246, 183, 60, 0.11); border: 1px solid rgba(246, 183, 60, 0.22); }
.issue-strip .critical { color: #ff9cab; background: rgba(255, 92, 114, 0.1); border: 1px solid rgba(255, 92, 114, 0.22); }

.signal-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.signal-card {
  min-height: 112px;
  padding: 16px;
  border: 1px solid rgba(146, 186, 220, 0.16);
  border-radius: 12px;
  background: linear-gradient(145deg, rgba(15, 42, 64, 0.92), rgba(9, 27, 43, 0.78));
  box-shadow: 0 12px 26px rgba(0, 0, 0, 0.16);
}

.signal-card.critical { border-color: rgba(255, 92, 114, 0.38); }
.signal-card.degraded { border-color: rgba(246, 183, 60, 0.35); }
.signal-top { justify-content: space-between; gap: 8px; color: var(--text-secondary); font-size: 13px; }
.signal-card > strong { display: block; margin: 15px 0 5px; font-size: 25px; }
.signal-card > small { color: var(--text-secondary); }

.workspace-grid,
.detail-grid {
  display: grid;
  gap: 16px;
  margin-bottom: 16px;
}

.workspace-grid { grid-template-columns: minmax(0, 1.55fr) minmax(360px, 0.8fr); }
.detail-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }

.ops-card {
  border: 1px solid rgba(146, 186, 220, 0.16);
  background: rgba(10, 31, 49, 0.88);
}

:deep(.ops-card .el-card__header) {
  border-bottom: 1px solid rgba(146, 186, 220, 0.13);
}

.card-title-row { justify-content: space-between; gap: 18px; }
.card-title-row > div:first-child { display: grid; gap: 4px; }
.card-title { font-size: 16px; font-weight: 650; }
.card-title-row > span { color: var(--text-secondary); font-size: 12px; }

.connection-list { display: grid; gap: 12px; }
.connection-block { padding: 13px; border: 1px solid rgba(146, 186, 220, 0.13); border-radius: 10px; background: rgba(5, 19, 31, 0.42); }
.connection-head { justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.connection-head > div { display: flex; align-items: center; gap: 8px; }
.connection-head span { color: var(--text-secondary); font-size: 12px; }
.catalog-version { opacity: 0.8; }

.metric-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; }
.metric-cell { padding: 10px; border-radius: 8px; border: 1px solid rgba(146, 186, 220, 0.12); background: rgba(9, 31, 48, 0.7); }
.metric-cell > span, .metric-cell > small { display: block; color: var(--text-secondary); font-size: 11px; }
.metric-cell > strong { display: block; margin: 7px 0 5px; font-size: 14px; white-space: nowrap; }
.metric-cell.fresh { border-color: rgba(45, 211, 111, 0.25); }
.metric-cell.stale, .metric-cell.degraded { border-color: rgba(246, 183, 60, 0.32); }
.metric-cell.missing { border-color: rgba(255, 92, 114, 0.36); }

.queue-summary,
.model-summary { gap: 14px; color: var(--text-secondary); font-size: 12px; }
.queue-summary strong,
.model-summary strong { color: var(--text-primary); font-size: 16px; }
.danger-text { color: #ff7385 !important; }
.table-actions { gap: 3px; }

.mono { font-family: Consolas, 'Roboto Mono', monospace; }
.digest { color: #89dff5; font-size: 12px; }

.ops-footer {
  justify-content: flex-end;
  gap: 20px;
  padding: 14px 2px 0;
  color: var(--text-secondary);
  font-size: 12px;
}

@media (max-width: 1380px) {
  .signal-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .workspace-grid { grid-template-columns: 1fr; }
}

@media (max-width: 980px) {
  .operations-center { padding: 16px; }
  .ops-header { align-items: flex-start; flex-direction: column; }
  .signal-grid, .detail-grid { grid-template-columns: 1fr; }
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .header-actions { width: 100%; justify-content: space-between; }
}
</style>
