<template>
  <div class="accuracy-report page-shell">
    <div class="page-header">
      <div>
        <h2>准确率/合格率报表</h2>
        <p>当前优先接入已落地的上报质量统计，展示完整率、及时率和各类型日报质量明细。</p>
      </div>
      <el-tag type="info" effect="dark">数据源：report/statistics</el-tag>
    </div>

    <div class="summary-grid">
      <el-card v-for="item in summaryCards" :key="item.key" class="summary-card">
        <div class="summary-label">{{ item.label }}</div>
        <div class="summary-value">{{ formatPercent(item.value) }}</div>
        <div class="summary-tip">{{ item.tip }}</div>
      </el-card>
    </div>

    <el-card class="card-shell">
      <div class="toolbar">
        <el-date-picker
          v-model="month"
          type="month"
          value-format="YYYY-MM"
          placeholder="选择统计月份"
          :clearable="false"
        />
        <el-select v-model="station" placeholder="选择场站" filterable>
          <el-option label="全部场站" value="all" />
          <el-option
            v-for="item in farms"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-button type="primary" :loading="loading" @click="loadStatistics">查询</el-button>
        <el-button :disabled="tableRows.length === 0" @click="exportReport">导出报表</el-button>
      </div>

      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="warning"
        show-icon
        :closable="false"
        class="result-alert"
      />

      <el-table v-loading="loading" :data="tableRows" border stripe empty-text="暂无质量统计数据">
        <el-table-column prop="farmName" label="场站" min-width="180" />
        <el-table-column prop="date" label="日期" width="120" />
        <el-table-column label="日完整率" width="120">
          <template #default="{ row }">
            <el-tag :type="row.completenessRate >= 90 ? 'success' : 'danger'">
              {{ formatPercent(row.completenessRate) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="日及时率" width="120">
          <template #default="{ row }">
            <el-tag :type="row.timelinessRate >= 90 ? 'success' : 'warning'">
              {{ formatPercent(row.timelinessRate) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="类型明细" min-width="320">
          <template #default="{ row }">
            <div class="type-list">
              <div
                v-for="item in row.typeEntries"
                :key="`${row.date}-${row.farmCode}-${item.type}`"
                class="type-item"
              >
                <span class="type-name">{{ getReportTypeName(item.type) }}</span>
                <span class="type-metric">完整率 {{ formatPercent(item.completeness_rate) }}</span>
                <span class="type-metric">及时率 {{ formatPercent(item.timeliness_rate) }}</span>
              </div>
              <span v-if="row.typeEntries.length === 0" class="type-empty">无类型明细</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="notes" label="备注" min-width="220" show-overflow-tooltip />
      </el-table>
    </el-card>
  </div>
</template>

<script>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getReportFarms, getReportStatistics } from '../api/reportApi'

const REPORT_TYPE_LABELS = {
  actual: '实际功率',
  forecast_short: '短期预测',
  forecast_long: '超短期预测',
  wind_speed: '风速报文',
  turbine_power: '机组功率',
  weather: '气象报文',
  installed_capacity: '装机容量',
  available_capacity: '可用容量',
  theoretical_power: '理论功率',
  available_power: '可发功率'
}

function normalizeFarmItem(item) {
  const farmCode = item?.farm_code || item?.code || item?.value || item?.id
  if (!farmCode) return null
  return {
    value: String(farmCode),
    label: item?.farm_name || item?.name || String(farmCode)
  }
}

function formatMonthDefault() {
  return new Date().toISOString().slice(0, 7)
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
  name: 'AccuracyReport',
  setup() {
    const month = ref(formatMonthDefault())
    const station = ref('all')
    const farms = ref([])
    const loading = ref(false)
    const errorMessage = ref('')
    const statistics = ref([])
    const todayStats = ref({ completeness_rate: null, timeliness_rate: null })
    const monthlyStats = ref({ completeness_rate: null, timeliness_rate: null })

    const formatPercent = (value) => {
      if (value === null || value === undefined || value === '') return '--'
      const numeric = Number(value)
      if (Number.isNaN(numeric)) return '--'
      return `${numeric.toFixed(2)}%`
    }

    const getReportTypeName = (type) => REPORT_TYPE_LABELS[type] || type || '--'

    const summaryCards = computed(() => [
      {
        key: 'today-completeness',
        label: '今日完整率',
        value: todayStats.value.completeness_rate,
        tip: '来自 report/statistics.today_stats.completeness_rate'
      },
      {
        key: 'today-timeliness',
        label: '今日及时率',
        value: todayStats.value.timeliness_rate,
        tip: '来自 report/statistics.today_stats.timeliness_rate'
      },
      {
        key: 'month-completeness',
        label: '本月完整率',
        value: monthlyStats.value.completeness_rate,
        tip: '来自 report/statistics.monthly_summary.completeness_rate'
      },
      {
        key: 'month-timeliness',
        label: '本月及时率',
        value: monthlyStats.value.timeliness_rate,
        tip: '来自 report/statistics.monthly_summary.timeliness_rate'
      }
    ])

    const tableRows = computed(() => {
      return (statistics.value || []).map((item) => {
        const typeEntries = Object.entries(item?.types || {}).map(([type, metrics]) => ({
          type,
          completeness_rate: Number(metrics?.completeness_rate || 0),
          timeliness_rate: Number(metrics?.timeliness_rate || 0)
        }))

        return {
          farmCode: item?.farm_code || '',
          farmName: item?.farm_name || item?.farm_code || '--',
          date: item?.date || '--',
          completenessRate: Number(item?.overall_completeness_rate || 0),
          timelinessRate: Number(item?.overall_timeliness_rate || 0),
          typeEntries,
          notes: item?.notes || ''
        }
      })
    })

    const loadFarms = async () => {
      try {
        const response = await getReportFarms()
        const items = Array.isArray(response.data) ? response.data : []
        farms.value = items.map(normalizeFarmItem).filter(Boolean)
      } catch (error) {
        console.error('加载上报场站失败:', error)
        farms.value = []
        ElMessage.error(error.response?.data?.error || '加载上报场站失败')
      }
    }

    const loadStatistics = async () => {
      loading.value = true
      errorMessage.value = ''
      try {
        const params = { month: month.value }
        if (station.value && station.value !== 'all') {
          params.farm_code = station.value
        }

        const response = await getReportStatistics(params)
        const payload = response.data || {}
        todayStats.value = payload.today_stats || { completeness_rate: null, timeliness_rate: null }
        monthlyStats.value = payload.monthly_summary || { completeness_rate: null, timeliness_rate: null }
        statistics.value = Array.isArray(payload.daily_stats) ? payload.daily_stats : []
      } catch (error) {
        console.error('加载质量统计失败:', error)
        statistics.value = []
        todayStats.value = { completeness_rate: null, timeliness_rate: null }
        monthlyStats.value = { completeness_rate: null, timeliness_rate: null }
        errorMessage.value = error.response?.data?.error || '加载质量统计失败，页面已回退为空表。'
        ElMessage.error(errorMessage.value)
      } finally {
        loading.value = false
      }
    }

    const exportReport = () => {
      if (tableRows.value.length === 0) {
        ElMessage.warning('当前没有可导出的报表数据')
        return
      }

      const header = ['场站', '日期', '日完整率', '日及时率', '类型明细', '备注']
      const rows = tableRows.value.map((item) => [
        item.farmName,
        item.date,
        formatPercent(item.completenessRate),
        formatPercent(item.timelinessRate),
        item.typeEntries.map((entry) => `${getReportTypeName(entry.type)}: ${formatPercent(entry.completeness_rate)}/${formatPercent(entry.timeliness_rate)}`).join(' | '),
        item.notes
      ])
      const csv = [header, ...rows]
        .map((line) => line.map((cell) => JSON.stringify(cell ?? '')).join(','))
        .join('\n')

      downloadTextFile(csv, `report-quality-${month.value}-${station.value || 'all'}.csv`)
      ElMessage.success('报表已导出到本地文件')
    }

    onMounted(async () => {
      await loadFarms()
      await loadStatistics()
    })

    return {
      month,
      station,
      farms,
      loading,
      errorMessage,
      summaryCards,
      tableRows,
      formatPercent,
      getReportTypeName,
      loadStatistics,
      exportReport
    }
  }
}
</script>

<style scoped>
.accuracy-report {
  min-height: 100%;
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
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

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.summary-card {
  background: rgba(6, 21, 34, 0.86);
  border: 1px solid rgba(130, 178, 212, 0.2);
}

.summary-label {
  color: var(--text-secondary);
  font-size: 13px;
}

.summary-value {
  margin-top: 8px;
  color: var(--text-primary);
  font-size: 26px;
  font-weight: 700;
}

.summary-tip {
  margin-top: 8px;
  color: var(--text-secondary);
  font-size: 12px;
}

.card-shell {
  background: rgba(6, 21, 34, 0.86);
  border: 1px solid rgba(130, 178, 212, 0.2);
}

.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.result-alert {
  margin-bottom: 12px;
}

.type-list {
  display: grid;
  gap: 6px;
}

.type-item {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  color: var(--text-primary);
  font-size: 13px;
}

.type-name {
  font-weight: 600;
}

.type-metric,
.type-empty {
  color: var(--text-secondary);
}

@media (max-width: 1100px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .page-header {
    flex-direction: column;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
