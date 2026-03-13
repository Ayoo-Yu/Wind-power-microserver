<template>
  <div class="audit-log page-shell">
    <div class="page-header">
      <div>
        <h2>操作日志审计</h2>
        <p>当前页面已切换为后端驱动的审计日志查询，筛选、排序和分页均由服务端完成。</p>
      </div>
      <el-tag type="info" effect="dark">数据源：auth/audit-logs</el-tag>
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
        <el-input v-model.trim="filters.module" placeholder="模块" clearable class="filter-item" />
        <el-select v-model="filters.result" clearable placeholder="结果" class="filter-item">
          <el-option label="成功" value="成功" />
          <el-option label="警告" value="警告" />
          <el-option label="失败" value="失败" />
        </el-select>
        <el-select v-model="filters.sortOrder" class="filter-item">
          <el-option label="时间倒序" value="desc" />
          <el-option label="时间正序" value="asc" />
        </el-select>
        <el-button :icon="Refresh" :loading="loading" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
        <el-button :disabled="logs.length === 0" @click="exportLogs">导出 CSV</el-button>
      </div>

      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="warning"
        show-icon
        :closable="false"
        class="result-alert"
      />

      <el-table :data="logs" v-loading="loading" border stripe empty-text="暂无审计日志">
        <el-table-column prop="operationTime" label="操作时间" min-width="180" />
        <el-table-column prop="operator" label="操作人" min-width="120" />
        <el-table-column prop="ipAddress" label="IP 地址" min-width="130" />
        <el-table-column prop="module" label="模块" min-width="140" />
        <el-table-column prop="operationType" label="操作类型" min-width="140" />
        <el-table-column prop="details" label="详情" min-width="420" show-overflow-tooltip />
        <el-table-column label="结果" width="92">
          <template #default="{ row }">
            <el-tag :type="row.result === '成功' ? 'success' : row.result === '失败' ? 'danger' : 'warning'" effect="plain">
              {{ row.result }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          background
          layout="total, sizes, prev, pager, next"
          :total="pagination.total"
          :page-size="pagination.perPage"
          :current-page="pagination.page"
          :page-sizes="[10, 20, 50, 100]"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script>
import { onMounted, reactive, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { listAuditLogs } from '../utils/auditLogStore'

function toDisplayTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('zh-CN', { hour12: false })
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
      result: '',
      sortOrder: 'desc'
    })
    const pagination = reactive({
      page: 1,
      perPage: 20,
      total: 0,
      pages: 0
    })

    const buildParams = () => {
      const params = {
        page: pagination.page,
        per_page: pagination.perPage,
        sort_order: filters.sortOrder
      }
      if (filters.operator) params.operator = filters.operator
      if (filters.module) params.module = filters.module
      if (filters.result) params.result = filters.result
      if (Array.isArray(filters.timeRange) && filters.timeRange.length === 2) {
        params.start_time = filters.timeRange[0]
        params.end_time = filters.timeRange[1]
      }
      return params
    }

    const fetchLogs = async () => {
      loading.value = true
      errorMessage.value = ''
      try {
        const response = await listAuditLogs(buildParams())
        const rows = Array.isArray(response?.logs) ? response.logs : []
        logs.value = rows.map((item) => ({
          ...item,
          operationTime: toDisplayTime(item.operationTime)
        }))
        pagination.total = Number(response?.total || 0)
        pagination.page = Number(response?.page || pagination.page)
        pagination.perPage = Number(response?.per_page || pagination.perPage)
        pagination.pages = Number(response?.pages || 0)
      } catch (error) {
        console.error('获取审计日志失败:', error)
        errorMessage.value = error?.response?.data?.message || '获取审计日志失败'
      } finally {
        loading.value = false
      }
    }

    const handleSearch = async () => {
      pagination.page = 1
      await fetchLogs()
    }

    const handleReset = async () => {
      filters.timeRange = []
      filters.operator = ''
      filters.module = ''
      filters.result = ''
      filters.sortOrder = 'desc'
      pagination.page = 1
      pagination.perPage = 20
      await fetchLogs()
    }

    const handlePageChange = async (page) => {
      pagination.page = page
      await fetchLogs()
    }

    const handleSizeChange = async (size) => {
      pagination.perPage = size
      pagination.page = 1
      await fetchLogs()
    }

    const exportLogs = () => {
      if (logs.value.length === 0) {
        ElMessage.warning('当前页没有可导出的审计日志')
        return
      }

      const header = ['操作时间', '操作人', 'IP 地址', '模块', '操作类型', '详情', '结果']
      const rows = logs.value.map((item) => [
        item.operationTime,
        item.operator,
        item.ipAddress,
        item.module,
        item.operationType,
        item.details,
        item.result
      ])
      const csv = [header, ...rows]
        .map((line) => line.map((cell) => JSON.stringify(cell ?? '')).join(','))
        .join('\n')

      downloadTextFile(csv, `audit-logs-page-${pagination.page}-${Date.now()}.csv`)
      ElMessage.success('当前页审计日志已导出')
    }

    onMounted(fetchLogs)

    return {
      loading,
      errorMessage,
      logs,
      filters,
      pagination,
      fetchLogs,
      handleSearch,
      handleReset,
      handlePageChange,
      handleSizeChange,
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

.pagination-wrap {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 960px) {
  .page-header {
    flex-direction: column;
  }

  .pagination-wrap {
    justify-content: flex-start;
  }
}
</style>
