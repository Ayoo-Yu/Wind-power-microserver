<template>
  <div class="operations-center" v-loading="loading">
    <header class="ops-header">
      <div>
        <h1>链路运行状态</h1>
        <p>查看场站实时数据、数值天气预报和预测任务的运行健康度。</p>
      </div>
      <div class="header-actions">
        <el-button :icon="Refresh" :loading="loading" @click="loadOverview">刷新数据</el-button>
      </div>
    </header>

    <section :class="['status-hero', overallState]">
      <div class="hero-status">
        <div class="hero-status-heading">
          <span class="hero-status-icon">
            <el-icon><CircleCheckFilled v-if="overallState === 'healthy'" /><WarningFilled v-else /></el-icon>
          </span>
          <div>
            <strong>链路整体{{ overallLabel }}</strong>
            <p>{{ overallDescription }}</p>
          </div>
        </div>

        <div class="hero-signal-grid">
          <article v-for="signal in heroSignals" :key="signal.key" class="hero-signal">
            <span>{{ signal.label }}</span>
            <strong>{{ signal.value }}</strong>
            <small>{{ signal.detail }}</small>
          </article>
        </div>

        <div class="hero-actions">
          <el-button type="primary" @click="goToAlarms">查看异常记录</el-button>
          <span>系统每 30 秒自动更新</span>
        </div>
      </div>
    </section>

    <section class="workspace-grid">
      <el-card class="ops-card scada-card" shadow="never">
        <template #header>
          <div class="card-title-row">
            <div>
              <span class="card-title">SCADA 五指标实时健康</span>
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
                <span>
                  <el-icon class="metric-label-icon"><component :is="metricIcon(metric.metric)" /></el-icon>
                  {{ metric.label }}
                </span>
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

      <el-card class="ops-card event-card" shadow="never">
        <template #header>
          <div class="card-title-row">
            <div>
              <span class="card-title">异常事件记录</span>
              <small>集中呈现当前链路异常，便于快速响应与处置</small>
            </div>
            <el-button text type="primary" @click="goToAlarms">查看全部</el-button>
          </div>
        </template>

        <div v-if="recentIssues.length" class="event-list">
          <article v-for="issue in recentIssues" :key="`${issue.domain}-${issue.message}`" class="event-item">
            <span :class="['event-dot', issue.severity]"></span>
            <div class="event-copy">
              <strong>{{ issue.message }}</strong>
              <small>{{ issueDomainLabel(issue.domain) }} · {{ formatDateTime(overview?.generated_at) }}</small>
            </div>
            <el-tag size="small" :type="issueTag(issue.severity)">{{ issueStateLabel(issue.severity) }}</el-tag>
          </article>
        </div>
        <div v-else class="event-empty">
          <strong>当前没有待处理异常</strong>
          <span>链路状态将在下一次自动刷新后更新</span>
        </div>
      </el-card>
    </section>

    <details class="governance-details">
      <summary>
        <div>
          <strong>运行治理详情</strong>
          <span>预测输入追溯、模型版本和高级治理操作</span>
        </div>
        <span class="summary-hint">展开查看</span>
      </summary>

      <div class="governance-content">
    <section class="detail-grid">
      <el-card class="ops-card" shadow="never">
        <template #header>
          <div class="card-title-row">
            <div>
              <span class="card-title">预测输入与输出追溯</span>
              <small>每次预测冻结输入、模型、目标区间和不可变输出摘要</small>
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
          <el-table-column label="输出账本" width="105">
            <template #default="{ row }">
              <el-tag size="small" :type="traceTag(row.output_trace_status)">
                {{ traceLabel(row.output_trace_status) }} {{ row.output_point_count || 0 }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="目标截止" min-width="145">
            <template #default="{ row }">{{ formatDateTime(row.output_target_end) }}</template>
          </el-table-column>
          <el-table-column label="240小时交付" width="115">
            <template #default="{ row }">
              <el-tag v-if="['medium', 'mid'].includes(row.task_type)" size="small" :type="deliveryTag(row)">
                {{ deliveryLabel(row) }}
              </el-tag>
              <span v-else class="muted-text">不适用</span>
            </template>
          </el-table-column>
          <el-table-column label="输入版本" min-width="135">
            <template #default="{ row }"><span class="mono digest">{{ shortDigest(row.dataset_version) }}</span></template>
          </el-table-column>
          <el-table-column label="输出版本" min-width="135">
            <template #default="{ row }"><span class="mono digest">{{ shortDigest(row.output_sha256) }}</span></template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card v-if="reportingEnabled" class="ops-card" shadow="never">
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
      </div>
    </details>

    <footer class="ops-footer">
      <span>当前场站：{{ currentFarm || '全部场站' }}</span>
      <span>生成时间：{{ formatDateTime(overview?.generated_at) }}</span>
      <span>磁盘：{{ formatBytes(overview?.storage?.free_bytes) }} 可用</span>
    </footer>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  CircleCheck,
  CircleCheckFilled,
  Lightning,
  Odometer,
  PieChart,
  Refresh,
  WarningFilled,
  WindPower
} from '@element-plus/icons-vue'
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
const router = useRouter()
const currentFarm = ref(farmService.getCurrentFarm())
const reportingEnabled = import.meta.env.VITE_REPORTING_ENABLED === 'true'
let refreshTimer = null

const canManageModels = computed(() => hasPermission(getStoredUser(), 'manage_tasks'))
const allIssues = computed(() => overview.value?.overall?.issues || [])
const issues = computed(() => allIssues.value.filter(
  issue => reportingEnabled || issue.domain !== 'reporting'
))
const recentIssues = computed(() => issues.value.slice(0, 4))
const overallState = computed(() => {
  if (!overview.value) return 'unknown'
  if (allIssues.value.length === issues.value.length) {
    return overview.value?.overall?.state || 'unknown'
  }
  if (issues.value.some(issue => ['critical', 'error', 'danger'].includes(issue.severity))) return 'critical'
  if (issues.value.length) return 'degraded'
  return 'healthy'
})
const issueCount = computed(() => issues.value.length)
const overallDescription = computed(() => ({
  healthy: 'SCADA、NWP 与预测任务链路均处于可用状态。',
  degraded: `当前有 ${issueCount.value} 项运行状态需要关注。`,
  critical: `当前有 ${issueCount.value} 项异常需要尽快处理。`
})[overallState.value] || '系统正在汇总当前链路状态。')
const scadaConnections = computed(() => overview.value?.scada?.connections || [])
const nwpBatches = computed(() => overview.value?.nwp?.latest_batches || [])
const inputSnapshots = computed(() => overview.value?.prediction?.latest_input_snapshots || [])
const reportFailures = computed(() => overview.value?.reporting?.latest_failures || [])
const modelVersions = computed(() => overview.value?.models?.recent_versions || [])
const modelCandidateCount = computed(() => overview.value?.models?.lifecycle_counts?.candidate || 0)

const overallLabel = computed(() => ({
  healthy: '稳定',
  degraded: '需关注',
  critical: '异常'
})[overallState.value] || '状态未知')

const signals = computed(() => {
  const data = overview.value || {}
  const predictionCounts = data.prediction?.status_counts || {}
  const failed = (predictionCounts.failed || 0) + (predictionCounts.failure || 0) + (predictionCounts.error || 0)
  const missingTrace = Number(data.prediction?.missing_output_trace_count || 0)
  const storageState = Number(data.storage?.used_percent || 0) >= 90
    ? 'critical'
    : (Number(data.storage?.used_percent || 0) >= 80 ? 'degraded' : 'healthy')
  const signalItems = [
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
      state: failed || missingTrace ? 'degraded' : 'healthy',
      value: `${Object.values(predictionCounts).reduce((sum, value) => sum + Number(value || 0), 0)} 次`,
      detail: `${failed} 次失败，${data.prediction?.output_point_count || 0} 个输出点，${missingTrace} 次缺少账本`
    },
    {
      key: 'storage',
      label: '运行磁盘',
      state: storageState,
      value: `${Number(data.storage?.used_percent || 0).toFixed(1)}%`,
      detail: `${formatBytes(data.storage?.free_bytes)} 可用`
    }
  ]
  if (reportingEnabled) {
    signalItems.splice(signalItems.length - 1, 0, {
      key: 'reporting',
      label: '可靠上报',
      state: data.reporting?.dead_count ? 'critical' : ((data.reporting?.pending_count || 0) > 0 ? 'degraded' : 'healthy'),
      value: `${data.reporting?.pending_count || 0} 条待处理`,
      detail: `${data.reporting?.dead_count || 0} 条死信`
    })
  }
  return signalItems
})

const heroSignals = computed(() => {
  const priority = ['scada', 'prediction', 'storage']
  return priority
    .map(key => signals.value.find(signal => signal.key === key))
    .filter(Boolean)
})

function goToAlarms() {
  router.push('/alarm-center')
}

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

function issueTag(severity) {
  if (['critical', 'error', 'danger'].includes(severity)) return 'danger'
  if (severity === 'warning') return 'warning'
  return 'info'
}

function issueStateLabel(severity) {
  return ['critical', 'error', 'danger'].includes(severity) ? '待处置' : '需关注'
}

function issueDomainLabel(domain) {
  return ({
    scada: 'SCADA 实时链路',
    nwp: 'NWP 数据接入',
    prediction: '预测任务',
    storage: '运行磁盘',
    reporting: '可靠上报'
  })[domain] || '运行保障'
}

function workerTag(status) {
  return ['running', 'connected'].includes(status) ? 'success' : (status === 'error' ? 'danger' : 'warning')
}

function workerLabel(status) {
  return ({ running: '运行中', connected: '已连接', connecting: '连接中', stopped: '已停止', error: '异常' })[status] || status || '未知'
}

function metricIcon(metric) {
  return ({
    actual_power: Lightning,
    wind_speed: WindPower,
    theoretical_power: Odometer,
    available_power: CircleCheck,
    availability_pct: PieChart
  })[metric] || Odometer
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
  return ({ supershort: '超短期', short: '短期', medium: '中期', mid: '中期' })[value] || value || '未知'
}

function snapshotTag(status) {
  return ({ ready: 'success', degraded: 'warning', blocked: 'danger' })[status] || 'info'
}

function snapshotLabel(status) {
  return ({ ready: '就绪', degraded: '降级', blocked: '阻断' })[status] || status || '未知'
}

function traceTag(status) {
  return ({ complete: 'success', partial: 'warning', missing: 'danger' })[status] || 'info'
}

function traceLabel(status) {
  return ({ complete: '完整', partial: '部分', missing: '缺失' })[status] || '未知'
}

function deliveryTag(row) {
  if (row.regulatory_delivery_ready) return 'success'
  return Number(row.output_point_count || 0) > 0 ? 'warning' : 'danger'
}

function deliveryLabel(row) {
  if (row.regulatory_delivery_ready) return '已就绪'
  const count = Number(row.output_point_count || 0)
  return count > 0 ? `当前仅${count}点` : '暂无输出'
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
  padding: 30px 32px 40px;
  color: var(--text-primary);
  background: var(--bg-root);
}

.ops-header,
.card-title-row,
.connection-head,
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
  margin-bottom: 16px;
}

.ops-header h1 {
  margin: 0 0 7px;
  font-size: 34px;
  font-weight: 680;
  letter-spacing: -0.035em;
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

.status-hero {
  min-height: 216px;
  margin-bottom: 16px;
  overflow: hidden;
  background-color: #ffffff;
  background-image: url('@/assets/wind-farm-hero.webp');
  background-repeat: no-repeat;
  background-position: center right;
  background-size: cover;
  border: 1px solid var(--border-color);
  border-radius: 18px;
}

.hero-status {
  width: min(720px, 64%);
  min-height: 216px;
  display: flex;
  flex-direction: column;
  padding: 24px 34px 20px;
}

.hero-status-heading {
  display: flex;
  align-items: center;
  gap: 14px;
}

.hero-status-icon {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  flex: 0 0 42px;
  color: #ffffff;
  background: var(--accent);
  border-radius: 50%;
  font-size: 24px;
}

.status-hero.degraded .hero-status-icon {
  background: var(--warning);
}

.status-hero.critical .hero-status-icon {
  background: var(--danger);
}

.hero-status-heading strong {
  display: block;
  margin-bottom: 4px;
  color: var(--text-primary);
  font-size: 24px;
  font-weight: 670;
}

.hero-status-heading p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
}

.hero-signal-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-top: 20px;
}

.hero-signal {
  min-width: 0;
  padding: 0 22px;
  border-left: 1px solid rgba(69, 89, 76, 0.14);
}

.hero-signal:first-child {
  padding-left: 0;
  border-left: 0;
}

.hero-signal > span,
.hero-signal > small {
  display: block;
  overflow: hidden;
  color: var(--text-secondary);
  white-space: nowrap;
  text-overflow: ellipsis;
}

.hero-signal > span {
  font-size: 12px;
}

.hero-signal > strong {
  display: block;
  margin: 7px 0 4px;
  color: var(--accent);
  font-size: 24px;
  font-weight: 680;
  font-variant-numeric: tabular-nums;
}

.hero-signal > small {
  font-size: 11px;
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: auto;
  padding-top: 16px;
}

.hero-actions > span {
  color: var(--text-muted);
  font-size: 12px;
}

.workspace-grid,
.detail-grid {
  display: grid;
  gap: 20px;
  margin-bottom: 20px;
}

.workspace-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.detail-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }

.scada-card {
  grid-column: 1 / -1;
}

:deep(.scada-card .el-card__header) {
  padding: 14px 18px !important;
}

:deep(.scada-card .el-card__body) {
  padding: 14px 18px !important;
}

.ops-card {
  border: 1px solid var(--border-color);
  background: #ffffff;
}

:deep(.ops-card .el-card__header) {
  border-bottom: 1px solid var(--border-color);
}

.card-title-row { justify-content: space-between; gap: 18px; }
.card-title-row > div:first-child { display: grid; gap: 4px; }
.card-title { font-size: 16px; font-weight: 650; }
.card-title-row > span { color: var(--text-secondary); font-size: 12px; }

.connection-list { display: grid; gap: 12px; }
.connection-block { padding: 2px 0 0; background: transparent; }
.connection-head { justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.connection-head > div { display: flex; align-items: center; gap: 8px; }
.connection-head span { color: var(--text-secondary); font-size: 12px; }
.catalog-version { opacity: 0.8; }

.event-list {
  display: grid;
}

.event-item {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  min-height: 58px;
  border-bottom: 1px solid var(--border-light);
}

.event-item:last-child {
  border-bottom: 0;
}

.event-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-muted);
}

.event-dot.warning { background: var(--warning); }
.event-dot.critical,
.event-dot.error,
.event-dot.danger { background: var(--danger); }

.event-copy {
  min-width: 0;
}

.event-copy strong,
.event-copy small {
  display: block;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.event-copy strong {
  margin-bottom: 5px;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 600;
}

.event-copy small {
  color: var(--text-muted);
  font-size: 11px;
}

.event-empty {
  min-height: 130px;
  display: grid;
  place-content: center;
  gap: 6px;
  text-align: center;
}

.event-empty strong {
  color: var(--text-primary);
  font-size: 14px;
}

.event-empty span {
  color: var(--text-muted);
  font-size: 12px;
}

.metric-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); }
.metric-cell { min-width: 0; padding: 8px 14px; border-left: 1px solid var(--border-color); background: transparent; }
.metric-cell:first-child { padding-left: 0; border-left: 0; }
.metric-cell > span,
.metric-cell > small { overflow: hidden; color: var(--text-secondary); font-size: 12px; white-space: nowrap; text-overflow: ellipsis; }
.metric-cell > span { display: flex; align-items: center; gap: 5px; }
.metric-cell > small { display: block; }
.metric-label-icon { flex: 0 0 auto; color: var(--primary); font-size: 13px; }
.metric-cell > strong { display: block; margin: 5px 0 3px; color: var(--text-primary); font-size: 18px; font-variant-numeric: tabular-nums; white-space: nowrap; }
.metric-cell.stale > strong, .metric-cell.degraded > strong { color: var(--warning); }
.metric-cell.missing > strong { color: var(--danger); }

.queue-summary,
.model-summary { gap: 14px; color: var(--text-secondary); font-size: 12px; }
.queue-summary strong,
.model-summary strong { color: var(--text-primary); font-size: 16px; }
.danger-text { color: var(--danger) !important; }
.table-actions { gap: 3px; }

.mono { font-family: var(--font-mono); }
.digest { color: var(--accent-blue); font-size: 12px; }

.governance-details {
  margin-top: 4px;
  border-top: 1px solid var(--border-color);
}

.governance-details > summary {
  min-height: 76px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  cursor: pointer;
  list-style: none;
}

.governance-details > summary::-webkit-details-marker {
  display: none;
}

.governance-details > summary > div {
  display: grid;
  gap: 5px;
}

.governance-details > summary strong {
  color: var(--text-primary);
  font-size: 16px;
}

.governance-details > summary span {
  color: var(--text-secondary);
  font-size: 12px;
}

.summary-hint {
  color: var(--accent) !important;
}

.governance-details[open] .summary-hint {
  visibility: hidden;
}

.governance-content {
  padding: 4px 0 8px;
}

.ops-footer {
  justify-content: flex-end;
  gap: 20px;
  padding: 20px 2px 0;
  color: var(--text-secondary);
  font-size: 12px;
}

@media (max-width: 1380px) {
  .workspace-grid { grid-template-columns: 1fr; }
  .hero-status { width: min(760px, 72%); }
}

@media (max-width: 980px) {
  .operations-center { padding: 16px; }
  .ops-header { align-items: flex-start; flex-direction: column; }
  .detail-grid { grid-template-columns: 1fr; }
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .metric-cell,
  .metric-cell:first-child { padding: 12px; border: 0; border-bottom: 1px solid var(--border-color); }
  .header-actions { width: 100%; justify-content: space-between; }
  .status-hero { background-position: 58% center; }
  .hero-status { width: 100%; background: rgba(255, 255, 255, 0.86); }
}

@media (max-width: 640px) {
  .ops-header h1 { font-size: 29px; }
  .status-hero,
  .hero-status { min-height: 0; }
  .hero-status { padding: 24px 20px; }
  .hero-signal-grid { grid-template-columns: 1fr; gap: 14px; }
  .hero-signal,
  .hero-signal:first-child { padding: 0 0 12px; border: 0; border-bottom: 1px solid rgba(69, 89, 76, 0.14); }
  .hero-actions { align-items: flex-start; flex-direction: column; }
  .metric-grid { grid-template-columns: 1fr; }
  .ops-footer { align-items: flex-start; flex-direction: column; gap: 7px; }
}
</style>
