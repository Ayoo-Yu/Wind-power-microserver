<template>
  <div class="accuracy-report page-shell">
    <div class="page-header">
      <div>
        <h2>准确率/合格率报表</h2>
        <p>按月份汇总各场站短期与超短期预测的准确率、合格率，并叠加免考标记统计。</p>
      </div>
      <el-tag type="success" effect="dark">数据源：report/accuracy-statistics</el-tag>
    </div>

    <div class="summary-grid">
      <el-card v-for="item in summaryCards" :key="item.key" class="summary-card">
        <div class="summary-label">{{ item.label }}</div>
        <div class="summary-value">{{ item.formatter ? item.formatter(item.value) : formatPercent(item.value) }}</div>
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

      <el-table v-loading="loading" :data="tableRows" border stripe empty-text="暂无准确率统计数据">
        <el-table-column prop="farmName" label="场站" min-width="180" />
        <el-table-column prop="month" label="月份" width="120" />
        <el-table-column label="综合准确率" width="130">
          <template #default="{ row }">
            <el-tag :type="resolveScoreTag(row.accuracyRate)">
              {{ formatPercent(row.accuracyRate) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="综合合格率" width="130">
          <template #default="{ row }">
            <el-tag :type="resolveScoreTag(row.qualifiedRate)">
              {{ formatPercent(row.qualifiedRate) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="短期预测" min-width="240">
          <template #default="{ row }">
            <div class="type-list">
              <div class="type-item">
                <span class="type-name">准确率</span>
                <span class="type-metric">{{ formatPercent(row.shortAccuracyRate) }}</span>
              </div>
              <div class="type-item">
                <span class="type-name">合格率</span>
                <span class="type-metric">{{ formatPercent(row.shortQualifiedRate) }}</span>
              </div>
              <div class="type-item">
                <span class="type-name">可比对点</span>
                <span class="type-metric">{{ row.shortPoints }}</span>
              </div>
              <div class="type-item">
                <span class="type-name">RMSE</span>
                <span class="type-metric">{{ formatNumber(row.shortRmse) }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="超短期预测" min-width="240">
          <template #default="{ row }">
            <div class="type-list">
              <div class="type-item">
                <span class="type-name">准确率</span>
                <span class="type-metric">{{ formatPercent(row.supershortAccuracyRate) }}</span>
              </div>
              <div class="type-item">
                <span class="type-name">合格率</span>
                <span class="type-metric">{{ formatPercent(row.supershortQualifiedRate) }}</span>
              </div>
              <div class="type-item">
                <span class="type-name">可比对点</span>
                <span class="type-metric">{{ row.supershortPoints }}</span>
              </div>
              <div class="type-item">
                <span class="type-name">RMSE</span>
                <span class="type-metric">{{ formatNumber(row.supershortRmse) }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="免考时长(小时)" width="140">
          <template #default="{ row }">
            {{ formatNumber(row.excludedHours) }}
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
import { getAccuracyStatistics, getReportFarms } from '../api/reportApi'

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
    const summary = ref({
      farm_count: 0,
      avg_accuracy_rate: null,
      avg_qualified_rate: null,
      avg_short_accuracy_rate: null,
      avg_short_qualified_rate: null,
      avg_supershort_accuracy_rate: null,
      avg_supershort_qualified_rate: null,
      total_excluded_hours: 0
    })
    const statistics = ref([])

    const formatPercent = (value) => {
      if (value === null || value === undefined || value === '') return '--'
      const numeric = Number(value)
      if (Number.isNaN(numeric)) return '--'
      return `${numeric.toFixed(2)}%`
    }

    const formatNumber = (value) => {
      if (value === null || value === undefined || value === '') return '--'
      const numeric = Number(value)
      if (Number.isNaN(numeric)) return '--'
      return numeric.toFixed(2)
    }

    const resolveScoreTag = (value) => {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return 'info'
      const numeric = Number(value)
      if (numeric >= 95) return 'success'
      if (numeric >= 90) return 'warning'
      return 'danger'
    }

    const summaryCards = computed(() => [
      {
        key: 'avg-accuracy',
        label: '平均综合准确率',
        value: summary.value.avg_accuracy_rate,
        tip: '短期与超短期准确率的场站均值'
      },
      {
        key: 'avg-qualified',
        label: '平均综合合格率',
        value: summary.value.avg_qualified_rate,
        tip: '短期与超短期合格率的场站均值'
      },
      {
        key: 'farm-count',
        label: '参与场站数',
        value: summary.value.farm_count,
        tip: '本月纳入统计的场站数量',
        formatter: (value) => `${value ?? 0}`
      },
      {
        key: 'excluded-hours',
        label: '免考时长',
        value: summary.value.total_excluded_hours,
        tip: '由质量标记累计的免考小时数',
        formatter: (value) => `${formatNumber(value)} h`
      }
    ])

    const tableRows = computed(() => {
      return (statistics.value || []).map((item) => ({
        farmCode: item?.farm_code || '',
        farmName: item?.farm_name || item?.farm_code || '--',
        month: item?.month || month.value,
        accuracyRate: item?.accuracy_rate,
        qualifiedRate: item?.qualified_rate,
        shortAccuracyRate: item?.short_accuracy_rate,
        shortQualifiedRate: item?.short_qualified_rate,
        supershortAccuracyRate: item?.supershort_accuracy_rate,
        supershortQualifiedRate: item?.supershort_qualified_rate,
        shortPoints: Number(item?.short_points || 0),
        supershortPoints: Number(item?.supershort_points || 0),
        shortRmse: item?.short_rmse,
        supershortRmse: item?.supershort_rmse,
        excludedHours: item?.excluded_hours,
        notes: item?.notes || ''
      }))
    })

    const loadFarms = async () => {
      try {
        const response = await getReportFarms()
        const items = Array.isArray(response.data) ? response.data : []
        farms.value = items.map(normalizeFarmItem).filter(Boolean)
      } catch (error) {
        console.error('加载报表场站失败:', error)
        farms.value = []
        ElMessage.error(error.response?.data?.error || '加载报表场站失败')
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

        const response = await getAccuracyStatistics(params)
        const payload = response.data || {}
        summary.value = payload.summary || {
          farm_count: 0,
          avg_accuracy_rate: null,
          avg_qualified_rate: null,
          total_excluded_hours: 0
        }
        statistics.value = Array.isArray(payload.items) ? payload.items : []
      } catch (error) {
        console.error('加载准确率统计失败:', error)
        statistics.value = []
        summary.value = {
          farm_count: 0,
          avg_accuracy_rate: null,
          avg_qualified_rate: null,
          avg_short_accuracy_rate: null,
          avg_short_qualified_rate: null,
          avg_supershort_accuracy_rate: null,
          avg_supershort_qualified_rate: null,
          total_excluded_hours: 0
        }
        errorMessage.value = error.response?.data?.error || '加载准确率/合格率统计失败'
        ElMessage.error(errorMessage.value)
      } finally {
        loading.value = false
      }
    }

    const exportReport = () => {
      if (tableRows.value.length === 0) {
        ElMessage.warning('当前没有可导出的统计数据')
        return
      }

      const header = [
        '场站',
        '月份',
        '综合准确率',
        '综合合格率',
        '短期准确率',
        '短期合格率',
        '超短期准确率',
        '超短期合格率',
        '短期可比对点',
        '超短期可比对点',
        '短期RMSE',
        '超短期RMSE',
        '免考时长(小时)',
        '备注'
      ]
      const rows = tableRows.value.map((item) => [
        item.farmName,
        item.month,
        formatPercent(item.accuracyRate),
        formatPercent(item.qualifiedRate),
        formatPercent(item.shortAccuracyRate),
        formatPercent(item.shortQualifiedRate),
        formatPercent(item.supershortAccuracyRate),
        formatPercent(item.supershortQualifiedRate),
        item.shortPoints,
        item.supershortPoints,
        formatNumber(item.shortRmse),
        formatNumber(item.supershortRmse),
        formatNumber(item.excludedHours),
        item.notes
      ])

      const csv = [header, ...rows]
        .map((line) => line.map((cell) => JSON.stringify(cell ?? '')).join(','))
        .join('\n')

      downloadTextFile(csv, `accuracy-report-${month.value}-${station.value || 'all'}.csv`)
      ElMessage.success('报表已导出')
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
      formatNumber,
      resolveScoreTag,
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
  background: var(--gradient-card);
  border: 1px solid var(--border-color);
}

.summary-label {
  color: var(--text-secondary);
  font-size: 13px;
}

.summary-value {
  margin-top: 8px;
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 26px;
  font-weight: 700;
}

.summary-tip {
  margin-top: 8px;
  color: var(--text-muted);
  font-size: 12px;
}

.card-shell {
  background: var(--gradient-card);
  border: 1px solid var(--border-color);
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
  justify-content: space-between;
  gap: 10px;
  color: var(--text-primary);
  font-size: 13px;
}

.type-name {
  font-weight: 600;
}

.type-metric {
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
