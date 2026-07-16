<template>
  <div class="database-governance page-shell" v-loading="loading">
    <header class="page-header">
      <div class="title-block">
        <div class="eyebrow">
          <el-icon><DataBoard /></el-icon>
          <span>DATABASE GOVERNANCE</span>
        </div>
        <h1>数据库治理</h1>
        <p class="subtitle">集中查看结构版本、表资产、索引健康和实时数据增长。</p>
      </div>

      <div class="header-actions">
        <div class="refresh-mode" :class="{ paused: !autoRefresh }">
          <span class="live-dot"></span>
          <span>{{ autoRefresh ? '60 秒自动刷新' : '自动刷新已暂停' }}</span>
          <el-switch v-model="autoRefresh" aria-label="自动刷新数据库状态" />
        </div>
        <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadOverview()">
          刷新状态
        </el-button>
      </div>
    </header>

    <el-alert
      v-if="overview && !overview.migration.ready"
      class="schema-alert"
      type="error"
      :closable="false"
      show-icon
      title="数据库结构版本未就绪"
      :description="migrationDescription"
    />

    <section class="overview-grid">
      <article :class="['health-card', `health-${structureHealth.state}`]">
        <div class="health-heading">
          <div class="health-icon">
            <el-icon><component :is="structureHealth.icon" /></el-icon>
          </div>
          <div>
            <span class="section-kicker">结构健康</span>
            <h2>{{ structureHealth.label }}</h2>
          </div>
          <el-tag :type="structureHealth.tagType" effect="dark" round>
            {{ structureHealth.tagText }}
          </el-tag>
        </div>

        <p class="health-description">{{ structureHealth.description }}</p>

        <div class="status-meta">
          <div>
            <span>数据库</span>
            <strong>{{ overview?.database?.name || '未知' }}</strong>
          </div>
          <div>
            <span>Schema</span>
            <strong>{{ overview?.database?.schema || 'public' }}</strong>
          </div>
          <div>
            <span>结构版本</span>
            <strong class="mono">{{ migrationRevision }}</strong>
          </div>
        </div>

        <div class="coverage-row">
          <div>
            <span>模型纳管覆盖率</span>
            <strong>{{ managedCoverage }}%</strong>
          </div>
          <el-progress
            :percentage="managedCoverage"
            :show-text="false"
            :stroke-width="7"
            :color="coverageColor"
          />
        </div>
      </article>

      <div class="signal-grid">
        <article v-for="item in signalCards" :key="item.key" class="signal-card">
          <div :class="['signal-icon', `tone-${item.tone}`]">
            <el-icon><component :is="item.icon" /></el-icon>
          </div>
          <div class="signal-copy">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
            <small>{{ item.detail }}</small>
          </div>
        </article>
      </div>
    </section>

    <section class="insight-grid">
      <el-card class="governance-card recommendation-card" shadow="never">
        <template #header>
          <div class="card-title-row">
            <div>
              <span class="card-title">治理关注项</span>
              <small>按影响程度排序，所有诊断均为只读</small>
            </div>
            <div class="attention-summary">
              <strong>{{ attentionCount }}</strong>
              <span>项需关注</span>
            </div>
          </div>
        </template>

        <div class="recommendation-list">
          <div
            v-for="item in visibleRecommendations"
            :key="`${item.title}-${item.detail}`"
            :class="['recommendation-item', `level-${item.level}`]"
          >
            <div class="recommendation-icon">
              <el-icon><component :is="recommendationIcon(item.level)" /></el-icon>
            </div>
            <div class="recommendation-copy">
              <div>
                <strong>{{ item.title }}</strong>
                <span>{{ recommendationLevel(item.level) }}</span>
              </div>
              <p>{{ item.detail }}</p>
            </div>
          </div>
        </div>
      </el-card>

      <el-card class="governance-card structure-card" shadow="never">
        <template #header>
          <div class="card-title-row">
            <div>
              <span class="card-title">结构约束</span>
              <small>快速定位会影响一致性和性能的结构问题</small>
            </div>
            <span class="generated-time">{{ formatDateTime(overview?.generated_at) }}</span>
          </div>
        </template>

        <div class="constraint-grid">
          <div v-for="item in constraintItems" :key="item.label" :class="item.state">
            <span>{{ item.label }}</span>
            <strong>{{ formatInteger(item.value) }}</strong>
            <small>{{ item.detail }}</small>
          </div>
        </div>
      </el-card>
    </section>

    <el-card class="governance-card table-card" shadow="never">
      <template #header>
        <div class="table-heading">
          <div>
            <span class="card-title">数据表资产</span>
            <small>空表经过存在性检查，行数使用数据库统计估算</small>
          </div>
          <div class="result-count">
            <strong>{{ filteredTables.length }}</strong>
            <span>/ {{ summary.total_tables }} 张表</span>
          </div>
        </div>
      </template>

      <div class="table-toolbar">
        <el-input v-model.trim="keyword" clearable placeholder="按表名搜索" class="search-input">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>

        <div class="category-tabs" role="group" aria-label="数据表分类筛选">
          <button
            v-for="item in categoryTabs"
            :key="item.value"
            type="button"
            :class="{ active: category === item.value }"
            :aria-pressed="category === item.value"
            @click="category = item.value"
          >
            <span>{{ item.label }}</span>
            <strong>{{ item.count }}</strong>
          </button>
        </div>

        <div class="toolbar-tail">
          <el-switch v-model="emptyOnly" active-text="只看空表" />
          <el-button v-if="filtersActive" text @click="resetFilters">清除筛选</el-button>
        </div>
      </div>

      <el-table
        :data="pagedTables"
        row-key="table_name"
        height="450"
        empty-text="没有符合条件的数据表"
      >
        <el-table-column label="表名" min-width="250">
          <template #default="{ row }">
            <div class="table-name-cell">
              <strong class="mono">{{ row.table_name }}</strong>
              <small>{{ partitionLabel(row) }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="归属" width="130">
          <template #default="{ row }">
            <el-tag :type="categoryTag(row.category)" effect="plain" round>
              {{ categoryLabel(row.category) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="数据状态" width="120">
          <template #default="{ row }">
            <span :class="['data-state', row.has_data ? 'has-data' : 'is-empty']">
              <i></i>{{ row.has_data ? '有数据' : '空表' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="估算行数" width="130" align="right">
          <template #default="{ row }">
            <span class="mono table-number">
              {{ row.row_estimate_available ? formatInteger(row.estimated_rows) : (row.has_data ? '≥ 1' : '0') }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="占用空间" width="130" align="right">
          <template #default="{ row }">
            <span class="mono table-number">{{ formatBytes(row.total_size_bytes) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="主键状态" width="120" align="center">
          <template #default="{ row }">
            <span :class="['key-state', row.has_primary_key ? 'ready' : 'attention']">
              {{ row.has_primary_key ? '已定义' : '待补充' }}
            </span>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-row">
        <span>当前显示 {{ pagedTables.length }} 张表</span>
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[15, 30, 50]"
          layout="total, sizes, prev, pager, next"
          :total="filteredTables.length"
        />
      </div>
    </el-card>

    <el-card v-if="overview?.duplicate_indexes?.length" class="governance-card duplicate-card" shadow="never">
      <template #header>
        <div class="table-heading">
          <div>
            <span class="card-title">潜在重复索引</span>
            <small>候选项仍需结合约束用途和查询计划确认</small>
          </div>
          <el-tag type="warning" effect="dark" round>
            {{ overview.duplicate_indexes.length }} 组
          </el-tag>
        </div>
      </template>
      <el-table :data="overview.duplicate_indexes" size="small" max-height="320">
        <el-table-column prop="table_name" label="表名" width="240" />
        <el-table-column label="索引">
          <template #default="{ row }">
            <span class="mono">{{ row.index_names.join('，') }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  CircleCheckFilled,
  CircleCloseFilled,
  Coin,
  DataBoard,
  Files,
  Refresh,
  Search,
  Timer,
  TrendCharts,
  WarningFilled
} from '@element-plus/icons-vue'
import { getDatabaseOverview } from '../api/systemApi'

const loading = ref(false)
const overview = ref(null)
const keyword = ref('')
const category = ref('all')
const emptyOnly = ref(false)
const autoRefresh = ref(true)
const currentPage = ref(1)
const pageSize = ref(15)
let refreshTimer = null

const summary = computed(() => overview.value?.summary || {
  total_tables: 0,
  managed_tables: 0,
  dynamic_tables: 0,
  empty_estimate_tables: 0,
  without_primary_key_tables: 0,
  total_size_bytes: 0,
  duplicate_index_groups: 0,
  foreign_keys: 0,
  unique_constraints: 0,
  primary_keys: 0
})

const dataTableCount = computed(() => Math.max(
  summary.value.total_tables - summary.value.empty_estimate_tables,
  0
))

const migrationRevision = computed(() => {
  const revisions = overview.value?.migration?.current_revisions || []
  return revisions.length ? revisions.join(', ') : '未记录'
})

const migrationDescription = computed(() => {
  const state = overview.value?.migration?.state
  if (state === 'pending') return '代码中存在待执行迁移，请先运行数据库升级命令。'
  if (state === 'unversioned') return '当前数据库尚未纳入版本管理，请先运行 prepare。'
  if (state === 'drift') return `缺少模型表：${(overview.value?.migration?.missing_tables || []).join('，')}`
  return '请检查数据库迁移状态。'
})

const managedCoverage = computed(() => {
  if (!summary.value.total_tables) return 0
  return Math.round((summary.value.managed_tables / summary.value.total_tables) * 100)
})

const coverageColor = computed(() => {
  if (managedCoverage.value >= 100) return '#2dd36f'
  if (managedCoverage.value >= 90) return '#12d7ff'
  return '#f6b73c'
})

const structureHealth = computed(() => {
  if (overview.value && !overview.value.migration?.ready) {
    return {
      state: 'critical',
      label: '结构未同步',
      description: '数据库版本与当前代码不一致，业务服务启动前需要先完成迁移。',
      tagText: '需立即处理',
      tagType: 'danger',
      icon: CircleCloseFilled
    }
  }
  const structureIssues = summary.value.without_primary_key_tables + summary.value.duplicate_index_groups
  const unmanaged = Number(overview.value?.categories?.unmanaged || 0)
  if (structureIssues || unmanaged) {
    return {
      state: 'attention',
      label: '存在治理项',
      description: `发现 ${structureIssues + unmanaged} 项结构问题，建议按下方清单逐项处理。`,
      tagText: '需要关注',
      tagType: 'warning',
      icon: WarningFilled
    }
  }
  return {
    state: 'healthy',
    label: '结构健康',
    description: '迁移版本、模型表、主键与索引检查均已通过。',
    tagText: '运行正常',
    tagType: 'success',
    icon: CircleCheckFilled
  }
})

const signalCards = computed(() => [
  {
    key: 'tables',
    label: '业务数据表',
    value: formatInteger(summary.value.total_tables),
    detail: `${formatInteger(dataTableCount.value)} 张有数据 · ${formatInteger(summary.value.empty_estimate_tables)} 张空表`,
    icon: Files,
    tone: 'cyan'
  },
  {
    key: 'storage',
    label: '数据库占用',
    value: formatBytes(summary.value.total_size_bytes),
    detail: `模型纳管 ${formatInteger(summary.value.managed_tables)} 张表`,
    icon: Coin,
    tone: 'violet'
  },
  {
    key: 'scada-hour',
    label: 'SCADA 最近一小时',
    value: formatInteger(overview.value?.scada_growth?.last_hour_rows),
    detail: overview.value?.scada_growth?.latest_received_at
      ? `最近接收 ${formatDateTime(overview.value.scada_growth.latest_received_at)}`
      : '暂未收到实时数据',
    icon: Timer,
    tone: 'green'
  },
  {
    key: 'scada-month',
    label: 'SCADA 30 天预测',
    value: formatInteger(overview.value?.scada_growth?.projected_30d_rows),
    detail: '按最近一小时接收速度估算',
    icon: TrendCharts,
    tone: 'amber'
  }
])

const attentionCount = computed(() => (
  (overview.value?.recommendations || []).filter(item => ['error', 'warning'].includes(item.level)).length
))

const visibleRecommendations = computed(() => (
  (overview.value?.recommendations || []).slice(0, 4)
))

const constraintItems = computed(() => [
  {
    label: '主键约束',
    value: summary.value.primary_keys,
    detail: summary.value.without_primary_key_tables ? '存在缺口' : '覆盖完整',
    state: summary.value.without_primary_key_tables ? 'warning' : 'healthy'
  },
  {
    label: '外键约束',
    value: summary.value.foreign_keys,
    detail: '关系完整性',
    state: 'neutral'
  },
  {
    label: '唯一约束',
    value: summary.value.unique_constraints,
    detail: '业务去重',
    state: 'neutral'
  },
  {
    label: '无主键表',
    value: summary.value.without_primary_key_tables,
    detail: summary.value.without_primary_key_tables ? '建议补充' : '无异常',
    state: summary.value.without_primary_key_tables ? 'warning' : 'healthy'
  },
  {
    label: '重复索引组',
    value: summary.value.duplicate_index_groups,
    detail: summary.value.duplicate_index_groups ? '可释放空间' : '无冗余',
    state: summary.value.duplicate_index_groups ? 'warning' : 'healthy'
  },
  {
    label: 'NWP 动态表',
    value: summary.value.dynamic_tables,
    detail: summary.value.dynamic_tables ? '按接入策略管理' : '当前未创建',
    state: 'neutral'
  }
])

const categoryTabs = computed(() => {
  const categories = overview.value?.categories || {}
  return [
    { label: '全部', value: 'all', count: summary.value.total_tables },
    { label: '模型纳管', value: 'managed', count: Number(categories.managed || 0) },
    {
      label: 'NWP 动态',
      value: 'nwp',
      count: Number(categories.nwp_parent || 0) + Number(categories.nwp_partition || 0)
    },
    { label: '未纳管', value: 'unmanaged', count: Number(categories.unmanaged || 0) }
  ]
})

const filteredTables = computed(() => {
  const normalized = keyword.value.toLowerCase()
  return (overview.value?.tables || []).filter((table) => {
    const matchesKeyword = !normalized || table.table_name.toLowerCase().includes(normalized)
    const matchesCategory = category.value === 'all'
      || table.category === category.value
      || (category.value === 'nwp' && ['nwp_parent', 'nwp_partition'].includes(table.category))
    const matchesEmpty = !emptyOnly.value || table.empty_estimate
    return matchesKeyword && matchesCategory && matchesEmpty
  })
})

const pagedTables = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredTables.value.slice(start, start + pageSize.value)
})

const filtersActive = computed(() => Boolean(
  keyword.value || category.value !== 'all' || emptyOnly.value
))

watch([keyword, category, emptyOnly, pageSize], () => {
  currentPage.value = 1
})

watch(autoRefresh, configureAutoRefresh)

function formatInteger(value) {
  return Number(value || 0).toLocaleString('zh-CN')
}

function formatBytes(value) {
  let amount = Number(value || 0)
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let unitIndex = 0
  while (amount >= 1024 && unitIndex < units.length - 1) {
    amount /= 1024
    unitIndex += 1
  }
  const digits = amount >= 100 || unitIndex === 0 ? 0 : 1
  return `${amount.toFixed(digits)} ${units[unitIndex]}`
}

function formatDateTime(value) {
  if (!value) return '未知'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function categoryLabel(value) {
  return {
    managed: '模型纳管',
    nwp_parent: 'NWP 父表',
    nwp_partition: 'NWP 月分区',
    unmanaged: '未纳管'
  }[value] || value
}

function categoryTag(value) {
  return {
    managed: 'success',
    nwp_parent: 'info',
    nwp_partition: 'info',
    unmanaged: 'warning'
  }[value] || 'info'
}

function partitionLabel(row) {
  if (row.is_partition) return '月度子分区'
  if (row.is_partitioned) return '分区父表'
  return '普通业务表'
}

function recommendationIcon(level) {
  if (level === 'error') return CircleCloseFilled
  if (level === 'warning') return WarningFilled
  return CircleCheckFilled
}

function recommendationLevel(level) {
  if (level === 'error') return '阻断'
  if (level === 'warning') return '关注'
  if (level === 'success') return '正常'
  return '建议'
}

function resetFilters() {
  keyword.value = ''
  category.value = 'all'
  emptyOnly.value = false
}

function configureAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
  if (autoRefresh.value) {
    refreshTimer = setInterval(() => {
      if (document.visibilityState === 'visible') {
        loadOverview(true)
      }
    }, 60000)
  }
}

async function loadOverview(silent = false) {
  if (!silent) loading.value = true
  try {
    const response = await getDatabaseOverview()
    overview.value = response.data
  } catch (error) {
    console.error('获取数据库治理概览失败:', error)
    if (!silent) {
      ElMessage.error(error.response?.data?.message || '获取数据库治理概览失败')
    }
  } finally {
    if (!silent) loading.value = false
  }
}

onMounted(() => {
  loadOverview()
  configureAutoRefresh()
})

onBeforeUnmount(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.database-governance {
  min-height: 100%;
  padding: 24px 26px 32px;
  color: var(--text-primary);
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 20px;
}

.title-block {
  min-width: 0;
}

.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 7px;
  color: #52d6c5;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2.1px;
}

.eyebrow .el-icon {
  font-size: 15px;
}

h1 {
  margin: 0;
  color: #fff;
  font-size: 30px;
  line-height: 1.2;
  letter-spacing: -0.4px;
}

.subtitle {
  margin: 9px 0 0;
  color: var(--text-secondary);
  font-size: 14px;
}

.header-actions,
.refresh-mode {
  display: flex;
  align-items: center;
}

.header-actions {
  gap: 10px;
}

.refresh-mode {
  gap: 8px;
  min-height: 34px;
  padding: 5px 10px;
  border: 1px solid rgba(45, 211, 111, 0.28);
  border-radius: 999px;
  background: rgba(45, 211, 111, 0.07);
  color: #a9c9ba;
  font-size: 12px;
}

.refresh-mode.paused {
  border-color: var(--border-color);
  background: rgba(159, 182, 204, 0.05);
  color: var(--text-muted);
}

.live-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent-2);
  box-shadow: var(--glow-success);
}

.paused .live-dot {
  background: var(--text-muted);
  box-shadow: none;
}

.schema-alert {
  margin-bottom: 16px;
}

.overview-grid {
  display: grid;
  grid-template-columns: minmax(320px, 0.82fr) minmax(0, 1.65fr);
  gap: 14px;
  margin-bottom: 14px;
}

.health-card,
.signal-card {
  border: 1px solid var(--border-color);
  border-radius: 14px;
  box-shadow: var(--shadow-soft), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.health-card {
  position: relative;
  overflow: hidden;
  min-height: 218px;
  padding: 20px;
  background: var(--surface);
}

.health-card::before {
  position: absolute;
  top: 0;
  left: 0;
  width: 4px;
  height: 100%;
  background: var(--accent-2);
  content: '';
}

.health-attention::before { background: var(--warning); }
.health-critical::before { background: var(--danger); }

.health-heading {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
}

.health-icon {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border: 1px solid rgba(45, 211, 111, 0.28);
  border-radius: 12px;
  background: rgba(45, 211, 111, 0.1);
  color: var(--accent-2);
  font-size: 22px;
}

.health-attention .health-icon {
  border-color: rgba(246, 183, 60, 0.3);
  background: rgba(246, 183, 60, 0.1);
  color: var(--warning);
}

.health-critical .health-icon {
  border-color: rgba(255, 93, 115, 0.3);
  background: rgba(255, 93, 115, 0.1);
  color: var(--danger);
}

.section-kicker {
  color: var(--text-muted);
  font-size: 11px;
}

.health-heading h2 {
  margin: 2px 0 0;
  color: #fff;
  font-size: 21px;
}

.health-description {
  min-height: 38px;
  margin: 14px 0 16px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.55;
}

.status-meta {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 0.75fr) minmax(0, 1.25fr);
  gap: 8px;
  margin-bottom: 14px;
}

.status-meta div {
  min-width: 0;
  padding: 9px 8px;
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.035);
}

.status-meta span,
.status-meta strong {
  display: block;
}

.status-meta span {
  margin-bottom: 4px;
  color: var(--text-muted);
  font-size: 10px;
}

.status-meta strong {
  overflow: hidden;
  color: #eaf4ff;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.coverage-row > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 7px;
  color: var(--text-secondary);
  font-size: 11px;
}

.coverage-row strong {
  color: #eaf4ff;
  font-size: 12px;
}

.signal-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.signal-card {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  align-items: center;
  gap: 14px;
  min-height: 102px;
  padding: 17px;
  background: var(--gradient-card);
}

.signal-icon {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border-radius: 12px;
  font-size: 20px;
}

.tone-cyan { background: rgba(18, 215, 255, 0.1); color: var(--accent); }
.tone-violet { background: rgba(167, 139, 250, 0.1); color: #a78bfa; }
.tone-green { background: rgba(45, 211, 111, 0.1); color: var(--accent-2); }
.tone-amber { background: rgba(246, 183, 60, 0.1); color: var(--warning); }

.signal-copy span,
.signal-copy strong,
.signal-copy small {
  display: block;
}

.signal-copy span {
  color: var(--text-secondary);
  font-size: 12px;
}

.signal-copy strong {
  margin: 5px 0;
  color: #fff;
  font-size: 24px;
  line-height: 1;
}

.signal-copy small {
  overflow: hidden;
  color: var(--text-muted);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.insight-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.12fr) minmax(390px, 0.88fr);
  gap: 14px;
  margin-bottom: 14px;
}

.governance-card {
  border: 1px solid var(--border-color);
  border-radius: 14px;
  background: var(--gradient-card);
}

:deep(.governance-card .el-card__header) {
  padding: 15px 18px;
  border-bottom-color: var(--border-color);
}

:deep(.governance-card .el-card__body) {
  padding: 16px 18px;
  color: var(--text-primary);
}

.card-title-row,
.table-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.card-title {
  display: block;
  color: #fff;
  font-size: 16px;
  font-weight: 650;
}

.card-title + small,
.card-title-row small,
.table-heading small {
  display: block;
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 11px;
}

.attention-summary,
.result-count {
  display: flex;
  align-items: baseline;
  gap: 5px;
  white-space: nowrap;
}

.attention-summary strong,
.result-count strong {
  color: var(--accent);
  font-size: 22px;
}

.attention-summary span,
.result-count span {
  color: var(--text-muted);
  font-size: 11px;
}

.recommendation-list {
  display: grid;
  gap: 9px;
}

.recommendation-item {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  gap: 10px;
  padding: 10px 11px;
  border: 1px solid rgba(146, 186, 220, 0.08);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.025);
}

.recommendation-icon {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border-radius: 9px;
  background: rgba(18, 215, 255, 0.08);
  color: var(--accent);
  font-size: 16px;
}

.level-warning .recommendation-icon {
  background: rgba(246, 183, 60, 0.09);
  color: var(--warning);
}

.level-error .recommendation-icon {
  background: rgba(255, 93, 115, 0.09);
  color: var(--danger);
}

.level-success .recommendation-icon {
  background: rgba(45, 211, 111, 0.09);
  color: var(--accent-2);
}

.recommendation-copy > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.recommendation-copy strong {
  color: #f3f9fd;
  font-size: 13px;
}

.recommendation-copy span {
  color: var(--text-muted);
  font-size: 10px;
}

.recommendation-copy p {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: 11px;
  line-height: 1.45;
}

.generated-time {
  color: var(--text-muted);
  font-size: 10px;
  white-space: nowrap;
}

.constraint-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 9px;
}

.constraint-grid > div {
  min-width: 0;
  padding: 10px 11px;
  border: 1px solid rgba(146, 186, 220, 0.08);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.025);
}

.constraint-grid span,
.constraint-grid strong,
.constraint-grid small {
  display: block;
}

.constraint-grid span {
  color: var(--text-muted);
  font-size: 10px;
}

.constraint-grid strong {
  margin: 5px 0 3px;
  color: #fff;
  font-size: 20px;
}

.constraint-grid small {
  color: var(--text-muted);
  font-size: 10px;
}

.constraint-grid .healthy strong,
.constraint-grid .healthy small { color: var(--accent-2); }
.constraint-grid .warning strong,
.constraint-grid .warning small { color: var(--warning); }

.table-card,
.duplicate-card {
  margin-bottom: 14px;
}

.table-toolbar {
  display: grid;
  grid-template-columns: minmax(190px, 0.85fr) minmax(420px, 1.55fr) auto;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.search-input {
  width: 100%;
}

.category-tabs {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 4px;
  padding: 4px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--surface-soft);
}

.category-tabs button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 30px;
  padding: 5px 8px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--text-secondary);
  font: inherit;
  font-size: 11px;
  cursor: pointer;
  transition: color var(--transition-fast), background var(--transition-fast);
}

.category-tabs button:hover {
  color: var(--primary);
  background: var(--surface);
}

.category-tabs button.active {
  background: var(--surface);
  color: var(--primary);
  box-shadow: inset 0 0 0 1px rgba(36, 122, 82, 0.22);
}

.category-tabs strong {
  min-width: 20px;
  padding: 1px 5px;
  border-radius: 999px;
  background: var(--bg-muted);
  color: inherit;
  font-size: 10px;
}

.toolbar-tail {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  white-space: nowrap;
}

:deep(.el-table) {
  --el-table-bg-color: #ffffff;
  --el-table-tr-bg-color: #ffffff;
  --el-table-row-hover-bg-color: #f4f8f5;
  --el-table-header-bg-color: #f7f9f7;
  --el-table-border-color: #e7ebe8;
  --el-table-text-color: #17211b;
  --el-table-header-text-color: #59645d;
}

:deep(.el-table th.el-table__cell) {
  height: 42px;
  font-size: 11px;
  font-weight: 600;
}

:deep(.el-table td.el-table__cell) {
  height: 48px;
  padding: 5px 0;
}

.table-name-cell strong,
.table-name-cell small {
  display: block;
}

.table-name-cell strong {
  overflow: hidden;
  color: #e9f5fd;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.table-name-cell small {
  margin-top: 3px;
  color: var(--text-muted);
  font-size: 10px;
}

.mono {
  font-family: var(--font-mono);
}

.table-number {
  color: #b9cfe0;
  font-size: 11px;
}

.data-state {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 11px;
}

.data-state i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.has-data { color: var(--accent-2); }
.is-empty { color: var(--text-muted); }

.key-state {
  display: inline-block;
  min-width: 54px;
  padding: 3px 7px;
  border-radius: 999px;
  font-size: 10px;
}

.key-state.ready {
  background: rgba(45, 211, 111, 0.08);
  color: #65dc91;
}

.key-state.attention {
  background: rgba(246, 183, 60, 0.1);
  color: var(--warning);
}

.pagination-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-top: 14px;
  color: var(--text-muted);
  font-size: 11px;
}

@media (max-width: 1160px) {
  .overview-grid,
  .insight-grid {
    grid-template-columns: 1fr;
  }

  .health-card {
    min-height: auto;
  }

  .table-toolbar {
    grid-template-columns: minmax(180px, 0.8fr) minmax(400px, 1.5fr);
  }

  .toolbar-tail {
    grid-column: 1 / -1;
  }
}

@media (max-width: 860px) {
  .database-governance {
    padding: 18px;
  }

  .page-header,
  .header-actions,
  .pagination-row {
    align-items: stretch;
    flex-direction: column;
  }

  .header-actions {
    width: 100%;
  }

  .refresh-mode {
    justify-content: space-between;
  }

  .table-toolbar {
    grid-template-columns: 1fr;
  }

  .toolbar-tail {
    grid-column: auto;
    justify-content: space-between;
  }

  .pagination-row :deep(.el-pagination) {
    justify-content: flex-start;
    overflow-x: auto;
  }
}

@media (max-width: 680px) {
  .signal-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 560px) {
  .constraint-grid,
  .status-meta,
  .category-tabs {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .health-heading {
    grid-template-columns: 42px minmax(0, 1fr);
  }

  .health-heading .el-tag {
    grid-column: 1 / -1;
    justify-self: start;
  }

  .card-title-row,
  .table-heading {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
