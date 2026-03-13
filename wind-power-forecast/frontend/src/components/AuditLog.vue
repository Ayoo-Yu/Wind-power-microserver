<template>
  <div class="audit-log page-shell">
    <div class="page-header">
      <div>
        <h2>操作日志审计</h2>
        <p>统一汇总前端本地审计日志和后端系统日志，并提供来源区分、筛选、导出能力。</p>
      </div>
      <el-tag type="info" effect="dark">本地审计 + 系统日志</el-tag>
    </div>

    <el-card class="card-shell">
      <div class="filters">
        <el-date-picker
          v-model="filters.timeRange"
          type="datetimerange"
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          format="YYYY-MM-DD HH:mm:ss"
          value-format="YYYY-MM-DD HH:mm:ss"
          class="filter-item"
        />
        <el-input v-model.trim="filters.operator" placeholder="操作人模糊搜索" clearable class="filter-item" />
        <el-select v-model="filters.module" clearable placeholder="模块" class="filter-item">
          <el-option v-for="item in moduleOptions" :key="item" :label="item" :value="item" />
        </el-select>
        <el-select v-model="filters.source" clearable placeholder="来源" class="filter-item">
          <el-option label="本地审计" value="local" />
          <el-option label="系统日志" value="remote" />
        </el-select>
        <el-button :icon="Refresh" :loading="loading" @click="fetchLogs">刷新</el-button>
        <el-button :disabled="filteredLogs.length === 0" @click="exportLogs">导出 CSV</el-button>
      </div>

      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="warning"
        show-icon
        :closable="false"
        class="result-alert"
      />

      <el-table :data="filteredLogs" v-loading="loading" border stripe empty-text="暂无日志">
        <el-table-column prop="operationTime" label="操作时间" min-width="180" />
        <el-table-column prop="operator" label="操作人" min-width="120" />
        <el-table-column prop="ipAddress" label="IP 地址" min-width="130" />
        <el-table-column prop="module" label="模块" min-width="120" />
        <el-table-column prop="operationType" label="操作类型" min-width="120" />
        <el-table-column label="来源" width="100">
          <template #default="{ row }">
            <el-tag :type="row.source === 'local' ? 'success' : 'info'" effect="plain">
              {{ row.source === 'local' ? '本地审计' : '系统日志' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="details" label="详情" min-width="420" show-overflow-tooltip />
        <el-table-column label="结果" width="92">
          <template #default="{ row }">
            <el-tag :type="row.result === '成功' ? 'success' : row.result === '失败' ? 'danger' : 'warning'" effect="plain">
              {{ row.result }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script>
import { computed, onMounted, reactive, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getSystemLogs } from '../api/systemApi'
import { listAuditLogs } from '../utils/auditLogStore'

function toDisplayTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('zh-CN', { hour12: false })
}

function normalizeResult(row) {
  const raw = row.result || row.level || ''
  const lower = String(raw).toLowerCase()
  if (lower.includes('error') || lower.includes('fail')) return '失败'
  if (lower.includes('warn')) return '预警'
  return '成功'
}

function parseSystemLogRow(row) {
  if (!row) return null
  if (typeof row === 'string') {
    return {
      operationTime: '-',
      rawTime: '',
      operator: 'system',
      ipAddress: '-',
      module: '系统',
      operationType: '系统日志',
      details: row,
      result: '成功',
      source: 'remote'
    }
  }

  const timestamp = row.operationTime || row.timestamp || row.time || ''
  return {
    operationTime: toDisplayTime(timestamp),
    rawTime: timestamp,
    operator: row.operator || row.user || row.username || 'system',
    ipAddress: row.ipAddress || row.ip || '-',
    module: row.module || row.source || '系统',
    operationType: row.operationType || row.action || '系统日志',
    details: row.details || row.message || JSON.stringify(row),
    result: normalizeResult(row),
    source: 'remote'
  }
}

function downloadTextFile(text, filename) {
  const blob = new Blob([text], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

export default {
  name: 'AuditLog',
  setup() {
    const loading = ref(false)
    const errorMessage = ref('')
    const logs = ref([])
    const filters = reactive({
      timeRange: [],
      operator: '',
      module: '',
      source: ''
    })

    const moduleOptions = computed(() => {
      return Array.from(new Set(logs.value.map(item => item.module).filter(Boolean)))
    })

    const filteredLogs = computed(() => {
      return logs.value.filter((item) => {
        if (filters.operator && !String(item.operator || '').toLowerCase().includes(filters.operator.toLowerCase())) {
          return false
        }
        if (filters.module && item.module !== filters.module) {
          return false
        }
        if (filters.source && item.source !== filters.source) {
          return false
        }
        if (Array.isArray(filters.timeRange) && filters.timeRange.length === 2) {
          const [start, end] = filters.timeRange.map(value => new Date(value).getTime())
          const current = new Date(item.rawTime || item.operationTime).getTime()
          if (!Number.isNaN(current) && (current < start || current > end)) {
            return false
          }
        }
        return true
      })
    })

    const fetchLogs = async () => {
      loading.value = true
      errorMessage.value = ''
      try {
        const localLogs = listAuditLogs().map(item => ({
          ...item,
          operationTime: toDisplayTime(item.operationTime),
          rawTime: item.operationTime,
          result: item.result || '成功',
          source: 'local'
        }))

        let remoteLogs = []
        try {
          const resp = await getSystemLogs()
          const data = resp?.data
          const rows = Array.isArray(data) ? data : Array.isArray(data?.logs) ? data.logs : []
          remoteLogs = rows.map(parseSystemLogRow).filter(Boolean)
        } catch (error) {
          console.error('加载远端系统日志失败:', error)
          errorMessage.value = error.response?.data?.error || '远端系统日志加载失败，页面已降级为仅展示本地审计日志。'
        }

        logs.value = [...localLogs, ...remoteLogs].sort((a, b) => {
          return String(b.rawTime || '').localeCompare(String(a.rawTime || ''))
        })
      } finally {
        loading.value = false
      }
    }

    const exportLogs = () => {
      if (filteredLogs.value.length === 0) {
        ElMessage.warning('当前没有可导出的日志')
        return
      }

      const header = ['操作时间', '操作人', 'IP 地址', '模块', '操作类型', '来源', '详情', '结果']
      const rows = filteredLogs.value.map((item) => [
        item.operationTime,
        item.operator,
        item.ipAddress,
        item.module,
        item.operationType,
        item.source === 'local' ? '本地审计' : '系统日志',
        item.details,
        item.result
      ])
      const csv = [header, ...rows]
        .map((line) => line.map((cell) => JSON.stringify(cell ?? '')).join(','))
        .join('\n')

      downloadTextFile(csv, `audit-logs-${Date.now()}.csv`)
      ElMessage.success('日志已导出到本地文件')
    }

    onMounted(fetchLogs)

    return {
      loading,
      errorMessage,
      logs,
      filters,
      moduleOptions,
      filteredLogs,
      fetchLogs,
      exportLogs,
      Refresh
    }
  }
}
</script>

<style scoped>
.audit-log {
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

.filters {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.filter-item {
  width: 220px;
}

.result-alert {
  margin-bottom: 12px;
}

@media (max-width: 960px) {
  .page-header {
    flex-direction: column;
  }
}
</style>
