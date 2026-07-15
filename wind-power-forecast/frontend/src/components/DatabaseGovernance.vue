<template>
  <div class="database-governance page-shell" v-loading="loading">
    <header class="page-header">
      <div>
        <p class="eyebrow">DATABASE GOVERNANCE</p>
        <h1>数据库治理</h1>
        <p class="subtitle">查看结构版本、容量、分区和数据增长情况。结构变更通过迁移文件完成。</p>
      </div>
      <el-button type="primary" :loading="loading" @click="loadOverview">
        <el-icon><Refresh /></el-icon>
        刷新状态
      </el-button>
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

    <section class="metric-grid">
      <article class="metric-card version-card">
        <span class="metric-label">结构版本</span>
        <strong>{{ migrationRevision }}</strong>
        <el-tag :type="overview?.migration?.ready ? 'success' : 'danger'" effect="dark">
          {{ overview?.migration?.ready ? '已同步' : '待处理' }}
        </el-tag>
      </article>
      <article class="metric-card">
        <span class="metric-label">业务表</span>
        <strong>{{ summary.total_tables }}</strong>
        <small>模型管理 {{ summary.managed_tables }} 张</small>
      </article>
      <article class="metric-card">
        <span class="metric-label">空表</span>
        <strong>{{ summary.empty_estimate_tables }}</strong>
        <small>通过统计信息和存在性检查识别</small>
      </article>
      <article class="metric-card">
        <span class="metric-label">数据库占用</span>
        <strong>{{ formatBytes(summary.total_size_bytes) }}</strong>
        <small>包含业务表及索引</small>
      </article>
      <article class="metric-card attention-card">
        <span class="metric-label">SCADA 最近一小时</span>
        <strong>{{ formatInteger(overview?.scada_growth?.last_hour_rows) }}</strong>
        <small>按当前速度 30 天约 {{ formatInteger(overview?.scada_growth?.projected_30d_rows) }} 行</small>
      </article>
    </section>

    <section class="content-grid">
      <el-card class="governance-card recommendation-card" shadow="never">
        <template #header>
          <div class="card-title-row">
            <div>
              <span class="card-title">治理建议</span>
              <small>只读诊断，不会修改数据库</small>
            </div>
            <span class="generated-time">更新于 {{ formatDateTime(overview?.generated_at) }}</span>
          </div>
        </template>
        <div class="recommendation-list">
          <div
            v-for="item in overview?.recommendations || []"
            :key="`${item.title}-${item.detail}`"
            :class="['recommendation-item', `level-${item.level}`]"
          >
            <span class="status-dot"></span>
            <div>
              <strong>{{ item.title }}</strong>
              <p>{{ item.detail }}</p>
            </div>
          </div>
        </div>
      </el-card>

      <el-card class="governance-card structure-card" shadow="never">
        <template #header>
          <span class="card-title">结构约束</span>
        </template>
        <div class="constraint-grid">
          <div><strong>{{ summary.primary_keys }}</strong><span>主键约束</span></div>
          <div><strong>{{ summary.foreign_keys }}</strong><span>外键约束</span></div>
          <div><strong>{{ summary.unique_constraints }}</strong><span>唯一约束</span></div>
          <div><strong>{{ summary.without_primary_key_tables }}</strong><span>无主键表</span></div>
          <div><strong>{{ summary.duplicate_index_groups }}</strong><span>重复索引组</span></div>
          <div><strong>{{ summary.dynamic_tables }}</strong><span>NWP 动态表</span></div>
        </div>
      </el-card>
    </section>

    <el-card class="governance-card table-card" shadow="never">
      <template #header>
        <div class="card-title-row table-toolbar">
          <div>
            <span class="card-title">数据表清单</span>
            <small>行数为数据库统计估算，空表状态经过存在性检查</small>
          </div>
          <div class="filters">
            <el-input v-model.trim="keyword" clearable placeholder="搜索表名" style="width: 220px" />
            <el-select v-model="category" style="width: 170px">
              <el-option label="全部分类" value="all" />
              <el-option label="模型管理" value="managed" />
              <el-option label="旧链路候选" value="legacy_candidate" />
              <el-option label="演示功能候选" value="demo_candidate" />
              <el-option label="NWP 父表" value="nwp_parent" />
              <el-option label="NWP 月分区" value="nwp_partition" />
              <el-option label="未纳入模型" value="unmanaged" />
            </el-select>
            <el-checkbox v-model="emptyOnly">只看空表</el-checkbox>
          </div>
        </div>
      </template>

      <el-table :data="pagedTables" stripe height="520" empty-text="没有符合条件的数据表">
        <el-table-column prop="table_name" label="表名" min-width="250" fixed />
        <el-table-column label="分类" width="140">
          <template #default="{ row }">
            <el-tag :type="categoryTag(row.category)" effect="plain">
              {{ categoryLabel(row.category) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="数据状态" width="110">
          <template #default="{ row }">
            <span :class="['data-state', row.has_data ? 'has-data' : 'is-empty']">
              {{ row.has_data ? '有数据' : '空表' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="估算行数" width="130" align="right">
          <template #default="{ row }">
            {{ row.row_estimate_available ? formatInteger(row.estimated_rows) : (row.has_data ? '≥ 1' : '0') }}
          </template>
        </el-table-column>
        <el-table-column label="占用空间" width="130" align="right">
          <template #default="{ row }">{{ formatBytes(row.total_size_bytes) }}</template>
        </el-table-column>
        <el-table-column label="主键" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.has_primary_key ? 'success' : 'warning'">
              {{ row.has_primary_key ? '有' : '无' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="分区角色" width="120">
          <template #default="{ row }">{{ partitionLabel(row) }}</template>
        </el-table-column>
      </el-table>

      <div class="pagination-row">
        <span>共 {{ filteredTables.length }} 张表</span>
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          layout="prev, pager, next"
          :total="filteredTables.length"
        />
      </div>
    </el-card>

    <el-card v-if="overview?.duplicate_indexes?.length" class="governance-card duplicate-card" shadow="never">
      <template #header>
        <div>
          <span class="card-title">潜在重复索引</span>
          <small>此处只提示候选项，仍需检查约束用途和执行计划</small>
        </div>
      </template>
      <el-table :data="overview.duplicate_indexes" size="small" max-height="320">
        <el-table-column prop="table_name" label="表名" width="220" />
        <el-table-column label="索引">
          <template #default="{ row }">{{ row.index_names.join('，') }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { getDatabaseOverview } from '../api/systemApi'

const loading = ref(false)
const overview = ref(null)
const keyword = ref('')
const category = ref('all')
const emptyOnly = ref(false)
const currentPage = ref(1)
const pageSize = 20

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

const filteredTables = computed(() => {
  const normalized = keyword.value.toLowerCase()
  return (overview.value?.tables || []).filter((table) => {
    const matchesKeyword = !normalized || table.table_name.toLowerCase().includes(normalized)
    const matchesCategory = category.value === 'all' || table.category === category.value
    const matchesEmpty = !emptyOnly.value || table.empty_estimate
    return matchesKeyword && matchesCategory && matchesEmpty
  })
})

const pagedTables = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredTables.value.slice(start, start + pageSize)
})

watch([keyword, category, emptyOnly], () => {
  currentPage.value = 1
})

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
    managed: '模型管理',
    legacy_candidate: '旧链路候选',
    demo_candidate: '演示功能候选',
    nwp_parent: 'NWP 父表',
    nwp_partition: 'NWP 月分区',
    unmanaged: '未纳入模型'
  }[value] || value
}

function categoryTag(value) {
  return {
    managed: 'success',
    legacy_candidate: 'warning',
    demo_candidate: 'warning',
    nwp_parent: 'info',
    nwp_partition: 'info',
    unmanaged: 'danger'
  }[value] || 'info'
}

function partitionLabel(row) {
  if (row.is_partition) return '子分区'
  if (row.is_partitioned) return '分区父表'
  return '普通表'
}

async function loadOverview() {
  loading.value = true
  try {
    const response = await getDatabaseOverview()
    overview.value = response.data
  } catch (error) {
    console.error('获取数据库治理概览失败:', error)
    ElMessage.error(error.response?.data?.message || '获取数据库治理概览失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadOverview)
</script>

<style scoped>
.database-governance {
  min-height: 100%;
  padding: 28px;
  color: #e8f4ff;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 22px;
}

.eyebrow {
  margin: 0 0 8px;
  color: #52d6c5;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 2.4px;
}

h1 {
  margin: 0;
  color: #fff;
  font-size: 30px;
  line-height: 1.2;
}

.subtitle {
  margin: 10px 0 0;
  color: rgba(222, 239, 251, 0.72);
  font-size: 14px;
}

.schema-alert {
  margin-bottom: 18px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}

.metric-card {
  min-height: 128px;
  padding: 20px;
  border: 1px solid rgba(119, 190, 226, 0.18);
  border-radius: 14px;
  background: linear-gradient(145deg, rgba(15, 46, 67, 0.92), rgba(8, 27, 43, 0.86));
  box-shadow: 0 12px 34px rgba(1, 12, 23, 0.2);
}

.metric-card strong {
  display: block;
  margin: 11px 0 7px;
  color: #fff;
  font-size: 28px;
  line-height: 1;
}

.metric-card small,
.metric-label {
  color: rgba(217, 237, 249, 0.66);
}

.version-card strong {
  font-size: 20px;
}

.version-card .el-tag {
  margin-top: 4px;
}

.attention-card {
  border-color: rgba(247, 184, 86, 0.28);
  background: linear-gradient(145deg, rgba(62, 48, 31, 0.88), rgba(21, 31, 41, 0.9));
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(330px, 0.75fr);
  gap: 16px;
  margin-bottom: 16px;
}

.governance-card {
  border: 1px solid rgba(119, 190, 226, 0.16);
  border-radius: 14px;
  background: rgba(7, 27, 43, 0.86);
}

:deep(.governance-card .el-card__header) {
  border-bottom-color: rgba(119, 190, 226, 0.14);
}

:deep(.governance-card .el-card__body),
:deep(.governance-card .el-card__header) {
  color: #deeffa;
}

.card-title-row,
.table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

.card-title {
  display: block;
  color: #fff;
  font-size: 17px;
  font-weight: 650;
}

.card-title + small,
.card-title-row small {
  display: block;
  margin-top: 4px;
  color: rgba(215, 235, 247, 0.58);
}

.generated-time {
  color: rgba(215, 235, 247, 0.5);
  font-size: 12px;
}

.recommendation-list {
  display: grid;
  gap: 10px;
}

.recommendation-item {
  display: grid;
  grid-template-columns: 10px 1fr;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.035);
}

.recommendation-item strong {
  color: #f5fbff;
  font-size: 14px;
}

.recommendation-item p {
  margin: 5px 0 0;
  color: rgba(220, 238, 249, 0.68);
  font-size: 13px;
  line-height: 1.55;
}

.status-dot {
  width: 8px;
  height: 8px;
  margin-top: 6px;
  border-radius: 50%;
  background: #52d6c5;
}

.level-warning .status-dot { background: #e6a23c; }
.level-error .status-dot { background: #f56c6c; }
.level-info .status-dot { background: #409eff; }

.constraint-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.constraint-grid div {
  padding: 14px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.035);
}

.constraint-grid strong {
  display: block;
  margin-bottom: 4px;
  color: #fff;
  font-size: 22px;
}

.constraint-grid span {
  color: rgba(217, 237, 249, 0.62);
  font-size: 12px;
}

.table-card,
.duplicate-card {
  margin-bottom: 16px;
}

.filters {
  display: flex;
  align-items: center;
  gap: 10px;
}

:deep(.el-table) {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-row-hover-bg-color: rgba(64, 158, 255, 0.1);
  --el-table-header-bg-color: rgba(32, 77, 103, 0.7);
  --el-table-border-color: rgba(119, 190, 226, 0.12);
  --el-table-text-color: #dcecf6;
  --el-table-header-text-color: #9fc5da;
}

.data-state {
  font-size: 13px;
}

.has-data { color: #67c23a; }
.is-empty { color: #909399; }

.pagination-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 16px;
  color: rgba(217, 237, 249, 0.58);
  font-size: 13px;
}

@media (max-width: 1280px) {
  .metric-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .content-grid { grid-template-columns: 1fr; }
}

@media (max-width: 860px) {
  .database-governance { padding: 18px; }
  .page-header,
  .table-toolbar,
  .filters { align-items: stretch; flex-direction: column; }
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .filters :deep(.el-input),
  .filters :deep(.el-select) { width: 100% !important; }
}
</style>
