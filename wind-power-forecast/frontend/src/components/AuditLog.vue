<template>
  <div class="audit-log page-shell">
    <div class="page-header">
      <h2>系统操作日志</h2>
      <p>只读审计页面，支持按时间、操作人、模块进行精确筛选</p>
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
        <el-input v-model.trim="filters.operator" placeholder="操作人" clearable class="filter-item" />
        <el-select v-model="filters.module" clearable placeholder="所属模块" class="filter-item">
          <el-option v-for="item in moduleOptions" :key="item" :label="item" :value="item" />
        </el-select>
        <el-button :icon="Refresh" :loading="loading" @click="fetchLogs">刷新</el-button>
      </div>

      <el-table :data="filteredLogs" v-loading="loading" border stripe>
        <el-table-column prop="operationTime" label="操作时间" min-width="180" />
        <el-table-column prop="operator" label="操作人" min-width="120" />
        <el-table-column prop="ipAddress" label="IP地址" min-width="130" />
        <el-table-column prop="module" label="所属模块" min-width="120" />
        <el-table-column prop="operationType" label="操作类型" min-width="120" />
        <el-table-column prop="details" label="操作详情" min-width="420" show-overflow-tooltip />
        <el-table-column label="操作结果" width="92">
          <template #default="{ row }">
            <el-tag :type="row.result === '成功' ? 'success' : 'danger'" effect="plain">{{ row.result }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script>
import { computed, onMounted, reactive, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { getSystemLogs } from '../api/systemApi'
import { listAuditLogs } from '../utils/auditLogStore'

const parseSystemLogRow = (row) => {
  if (!row) return null
  if (typeof row === 'string') {
    return {
      operationTime: '-',
      operator: 'system',
      ipAddress: '-',
      module: '系统',
      operationType: '日志',
      details: row,
      result: '成功'
    }
  }
  return {
    operationTime: row.operationTime || row.timestamp || row.time || '-',
    operator: row.operator || row.user || row.username || 'system',
    ipAddress: row.ipAddress || row.ip || '-',
    module: row.module || row.source || '系统',
    operationType: row.operationType || row.action || '日志',
    details: row.details || row.message || JSON.stringify(row),
    result: row.result || (String(row.level || '').toLowerCase().includes('error') ? '失败' : '成功')
  }
}

export default {
  name: 'AuditLog',
  setup() {
    const loading = ref(false)
    const logs = ref([])
    const filters = reactive({
      timeRange: [],
      operator: '',
      module: ''
    })

    const moduleOptions = computed(() => {
      return Array.from(new Set(logs.value.map(item => item.module).filter(Boolean)))
    })

    const filteredLogs = computed(() => {
      return logs.value.filter(item => {
        if (filters.operator && item.operator !== filters.operator) return false
        if (filters.module && item.module !== filters.module) return false
        if (Array.isArray(filters.timeRange) && filters.timeRange.length === 2) {
          const [start, end] = filters.timeRange.map(value => new Date(value).getTime())
          const current = new Date(item.operationTime).getTime()
          if (!Number.isNaN(current) && (current < start || current > end)) return false
        }
        return true
      })
    })

    const fetchLogs = async () => {
      loading.value = true
      try {
        const localLogs = listAuditLogs().map(item => ({
          ...item,
          operationTime: new Date(item.operationTime).toLocaleString('zh-CN', { hour12: false })
        }))

        let remoteRows = []
        try {
          const resp = await getSystemLogs()
          const data = resp?.data
          remoteRows = Array.isArray(data) ? data : Array.isArray(data?.logs) ? data.logs : []
        } catch (error) {
          remoteRows = []
        }

        const remoteLogs = remoteRows
          .map(parseSystemLogRow)
          .filter(Boolean)
          .map(item => ({
            ...item,
            operationTime: item.operationTime === '-' ? '-' : new Date(item.operationTime).toLocaleString('zh-CN', { hour12: false })
          }))

        logs.value = [...localLogs, ...remoteLogs]
      } finally {
        loading.value = false
      }
    }

    onMounted(fetchLogs)

    return {
      loading,
      logs,
      filters,
      moduleOptions,
      filteredLogs,
      fetchLogs,
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

.page-header h2 {
  margin: 0;
  color: var(--text-primary);
}

.page-header p {
  margin: 8px 0 14px;
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
</style>
