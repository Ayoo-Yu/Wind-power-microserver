<template>
  <div class="workspace page-shell">
    <div class="header">
      <div>
        <h2>人工修正工作台</h2>
        <p>基于现有上报配置加载真实预览数据，支持按比例、平移和限高方式修正后再调用手工上报接口提交。</p>
      </div>
      <el-tag type="warning" effect="dark">数据源：report/configs + preview-report + manual-report</el-tag>
    </div>

    <div class="layout">
      <el-card class="side">
        <el-form label-width="96px">
          <el-form-item label="场站">
            <el-select v-model="station" filterable placeholder="选择场站" @change="handleStationChange">
              <el-option
                v-for="item in farms"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="目标日期">
            <el-date-picker v-model="targetDate" type="date" value-format="YYYY-MM-DD" />
          </el-form-item>
          <el-form-item label="报文类型">
            <el-select v-model="reportType" @change="handleReportTypeChange">
              <el-option
                v-for="item in reportTypeOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="上报配置">
            <el-select v-model="selectedConfigId" filterable placeholder="选择配置">
              <el-option
                v-for="item in availableConfigs"
                :key="item.id"
                :label="buildConfigLabel(item)"
                :value="item.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="修正工具">
            <el-select v-model="tool">
              <el-option label="按比例调整(%)" value="scaleUp" />
              <el-option label="整体平移(MW)" value="shift" />
              <el-option label="限制上限(MW)" value="cap" />
            </el-select>
          </el-form-item>
          <el-form-item label="修正值">
            <el-input-number v-model="toolValue" :min="-1000" :max="1000" />
          </el-form-item>
        </el-form>

        <div class="config-meta">
          <div class="meta-item">
            <span class="meta-label">当前配置</span>
            <span class="meta-value">{{ currentConfig ? buildConfigLabel(currentConfig) : '未选择' }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">原始点数</span>
            <span class="meta-value">{{ originalRows.length }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">当前点数</span>
            <span class="meta-value">{{ points.length }}</span>
          </div>
        </div>

        <div class="actions">
          <el-button type="primary" :loading="loading" @click="loadPreviewData">加载数据</el-button>
          <el-button :disabled="points.length === 0" @click="applyTool">应用修正</el-button>
          <el-button :disabled="originalRows.length === 0" @click="resetSeries">恢复原始值</el-button>
          <el-button
            type="success"
            :disabled="points.length === 0 || !selectedConfigId"
            :loading="saving"
            @click="saveVersion"
          >
            保存并上报
          </el-button>
        </div>
      </el-card>

      <div class="content">
        <el-alert
          v-if="errorMessage"
          :title="errorMessage"
          type="warning"
          show-icon
          :closable="false"
          class="content-alert"
        />

        <el-card class="chart-card">
          <div class="chart-header">
            <div>
              <div class="chart-title">修正曲线</div>
              <div class="chart-tip">
                当前展示 {{ getReportTypeName(reportType) }} 的归一化序列。保存时会回写为后端要求的报文结构。
              </div>
            </div>
            <el-tag v-if="previewMeta.loadedAt" type="info">{{ previewMeta.loadedAt }}</el-tag>
          </div>

          <svg v-if="points.length > 0" viewBox="0 0 960 360" class="chart">
            <polyline
              :points="baselinePoints"
              fill="none"
              stroke="rgba(148, 163, 184, 0.85)"
              stroke-width="2"
              stroke-dasharray="6 4"
            />
            <polyline
              :points="linePoints"
              fill="none"
              stroke="#18d8ff"
              stroke-width="3"
            />
            <line
              v-if="capValue !== null"
              x1="0"
              x2="960"
              :y1="toY(capValue)"
              :y2="toY(capValue)"
              stroke="#fbbf24"
              stroke-width="2"
              stroke-dasharray="8 5"
            />
          </svg>
          <el-empty v-else description="请先加载上报预览数据" />
        </el-card>

        <el-card class="table-card">
          <div class="table-title">修正点明细</div>
          <el-table :data="points" border stripe empty-text="暂无可编辑数据">
            <el-table-column prop="label" label="时点/序号" min-width="140" />
            <el-table-column prop="sourceValue" label="原始值" width="120">
              <template #default="{ row }">{{ formatNumber(row.sourceValue) }}</template>
            </el-table-column>
            <el-table-column label="修正值" width="180">
              <template #default="{ row, $index }">
                <el-input-number
                  :model-value="row.value"
                  :min="0"
                  :max="999999"
                  :precision="2"
                  @update:model-value="updatePointValue($index, $event)"
                />
              </template>
            </el-table-column>
            <el-table-column prop="time" label="原始时间" min-width="180" show-overflow-tooltip />
          </el-table>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getReportConfigs, getReportFarms, manualReport, previewReport } from '../api/reportApi'
import { hasAnyPermission } from '../utils/permission'

const REPORT_TYPE_OPTIONS = [
  { value: 'forecast_long', label: '超短期预测' },
  { value: 'forecast_short', label: '短期预测' },
  { value: 'actual', label: '实际功率' }
]

const REPORT_TYPE_LABELS = REPORT_TYPE_OPTIONS.reduce((acc, item) => {
  acc[item.value] = item.label
  return acc
}, {})

function normalizeFarmItem(item) {
  const farmCode = item?.farm_code || item?.code || item?.value || item?.id
  if (!farmCode) return null
  return {
    value: String(farmCode),
    label: item?.farm_name || item?.name || String(farmCode)
  }
}

function formatDateDefault() {
  return new Date().toISOString().slice(0, 10)
}

function buildNowLabel() {
  return `最近加载：${new Date().toLocaleString('zh-CN')}`
}

function safeArray(value) {
  return Array.isArray(value) ? value : []
}

export default {
  name: 'ManualInterventionWorkspace',
  setup() {
    const route = useRoute()
    const station = ref('')
    const targetDate = ref(formatDateDefault())
    const reportType = ref('forecast_long')
    const tool = ref('scaleUp')
    const toolValue = ref(10)
    const capValue = ref(null)
    const farms = ref([])
    const configs = ref([])
    const selectedConfigId = ref(null)
    const loading = ref(false)
    const saving = ref(false)
    const errorMessage = ref('')
    const originalRows = ref([])
    const points = ref([])
    const previewMeta = ref({ loadedAt: '', sourceType: '' })

    const reportTypeOptions = REPORT_TYPE_OPTIONS

    const getReportTypeName = (type) => REPORT_TYPE_LABELS[type] || type || '--'

    const availableConfigs = computed(() => {
      return configs.value.filter((item) => item.report_type === reportType.value)
    })

    const currentConfig = computed(() => {
      return availableConfigs.value.find((item) => String(item.id) === String(selectedConfigId.value)) || null
    })

    const maxY = computed(() => {
      const values = points.value.map((item) => Number(item.value || 0))
      const sourceValues = points.value.map((item) => Number(item.sourceValue || 0))
      const cap = capValue.value === null ? 0 : Number(capValue.value)
      return Math.max(...values, ...sourceValues, cap, 1)
    })

    const toY = (value) => 330 - (Number(value || 0) / maxY.value) * 300
    const toX = (index) => (index / Math.max(points.value.length - 1, 1)) * 960

    const linePoints = computed(() => points.value.map((item, index) => `${toX(index)},${toY(item.value)}`).join(' '))
    const baselinePoints = computed(() => points.value.map((item, index) => `${toX(index)},${toY(item.sourceValue)}`).join(' '))

    const formatNumber = (value) => {
      const numeric = Number(value)
      if (Number.isNaN(numeric)) return '--'
      return numeric.toFixed(2)
    }

    const canSaveManual = () => hasAnyPermission(['manual_intervention_workspace', 'manage_reports', 'auto_predictions'])

    const buildConfigLabel = (config) => {
      const name = config?.config_name || config?.target_name || `配置${config?.id || ''}`
      return `${name} / ${getReportTypeName(config?.report_type)}`
    }

    const normalizePointSeries = (type, payloadRows, dateText) => {
      const rows = safeArray(payloadRows)

      if (type === 'forecast_short') {
        const row = rows[0] || {}
        const keys = Object.keys(row).filter((key) => /^wp_pred\d+$/.test(key)).sort((a, b) => Number(a.replace('wp_pred', '')) - Number(b.replace('wp_pred', '')))
        return keys.map((key) => ({
          key,
          label: key.replace('wp_pred', 'P'),
          time: row.time || `${dateText} 00:00:00`,
          value: Number(row[key] || 0),
          sourceValue: Number(row[key] || 0)
        }))
      }

      return rows
        .filter((item) => {
          if (!item?.time) return true
          return String(item.time).slice(0, 10) === dateText
        })
        .map((item, index) => {
          const baseValue = Number(item?.value ?? item?.wp_true ?? 0)
          return {
            key: String(item?.time || index),
            label: item?.time ? String(item.time).slice(11, 16) : `P${index + 1}`,
            time: item?.time || '',
            value: baseValue,
            sourceValue: baseValue
          }
        })
    }

    const denormalizePayload = () => {
      if (reportType.value === 'forecast_short') {
        const baseRow = { ...(originalRows.value[0] || {}) }
        points.value.forEach((item) => {
          baseRow[item.key] = Number(item.value || 0)
        })
        return [baseRow]
      }

      return safeArray(originalRows.value).map((item, index) => {
        const point = points.value[index]
        if (!point) return item
        return {
          ...item,
          value: Number(point.value || 0),
          wp_true: reportType.value === 'actual' ? Number(point.value || 0) : item.wp_true
        }
      })
    }

    const applyTool = () => {
      if (points.value.length === 0) {
        ElMessage.warning('请先加载可修正的数据')
        return
      }

      if (tool.value === 'scaleUp') {
        const factor = 1 + Number(toolValue.value) / 100
        points.value = points.value.map((item) => ({
          ...item,
          value: Number(Math.max(0, item.value * factor).toFixed(2))
        }))
      } else if (tool.value === 'shift') {
        points.value = points.value.map((item) => ({
          ...item,
          value: Number(Math.max(0, item.value + Number(toolValue.value)).toFixed(2))
        }))
      } else if (tool.value === 'cap') {
        capValue.value = Number(toolValue.value)
        points.value = points.value.map((item) => ({
          ...item,
          value: Number(Math.min(item.value, capValue.value).toFixed(2))
        }))
      }
    }

    const resetSeries = () => {
      capValue.value = null
      points.value = normalizePointSeries(reportType.value, originalRows.value, targetDate.value)
    }

    const updatePointValue = (index, value) => {
      points.value[index] = {
        ...points.value[index],
        value: Number(value || 0)
      }
      points.value = [...points.value]
    }

    const loadFarms = async () => {
      const response = await getReportFarms()
      farms.value = safeArray(response.data).map(normalizeFarmItem).filter(Boolean)
      if (!station.value && farms.value.length > 0) {
        station.value = farms.value[0].value
      }
    }

    const loadConfigs = async () => {
      if (!station.value) {
        configs.value = []
        selectedConfigId.value = null
        return
      }

      const response = await getReportConfigs({ farm_code: station.value })
      const items = safeArray(response.data)
      configs.value = items.filter((item) => {
        const code = item?.farm_code || item?.farm?.farm_code
        return !code || String(code) === String(station.value)
      })

      const currentExists = availableConfigs.value.some((item) => String(item.id) === String(selectedConfigId.value))
      if (!currentExists) {
        selectedConfigId.value = availableConfigs.value[0]?.id || null
      }
    }

    const loadPreviewData = async () => {
      if (!selectedConfigId.value) {
        ElMessage.warning('当前报文类型下没有可用上报配置')
        return
      }

      loading.value = true
      errorMessage.value = ''
      try {
        const response = await previewReport(selectedConfigId.value)
        const payloadRows = safeArray(response.data?.payload?.data)
        originalRows.value = payloadRows
        points.value = normalizePointSeries(reportType.value, payloadRows, targetDate.value)
        previewMeta.value = {
          loadedAt: buildNowLabel(),
          sourceType: response.data?.config_info?.report_type || reportType.value
        }

        if (points.value.length === 0) {
          errorMessage.value = '当前日期没有可修正数据，请切换日期或配置。'
          ElMessage.warning(errorMessage.value)
        } else {
          ElMessage.success(`已加载 ${points.value.length} 个修正点`)
        }
      } catch (error) {
        console.error('加载人工修正预览失败:', error)
        originalRows.value = []
        points.value = []
        previewMeta.value = { loadedAt: '', sourceType: '' }
        errorMessage.value = error.response?.data?.error || '加载人工修正预览失败'
        ElMessage.error(errorMessage.value)
      } finally {
        loading.value = false
      }
    }

    const saveVersion = async () => {
      if (!canSaveManual()) {
        ElMessage.warning('当前账号没有提交人工修正的权限')
        return
      }
      if (!selectedConfigId.value || points.value.length === 0) {
        ElMessage.warning('请先加载并修正数据')
        return
      }

      saving.value = true
      try {
        const payload = {
          config_id: selectedConfigId.value,
          data: denormalizePayload()
        }
        await manualReport(payload)
        ElMessage.success(`已提交 ${station.value} ${targetDate.value} 的人工修正结果`)
      } catch (error) {
        console.error('提交人工修正失败:', error)
        ElMessage.error(error.response?.data?.error || '提交人工修正失败')
      } finally {
        saving.value = false
      }
    }

    const handleStationChange = async () => {
      await loadConfigs()
      points.value = []
      originalRows.value = []
      errorMessage.value = ''
    }

    const handleReportTypeChange = () => {
      const fallback = availableConfigs.value[0]?.id || null
      selectedConfigId.value = fallback
      points.value = []
      originalRows.value = []
      errorMessage.value = ''
    }

    onMounted(async () => {
      const routeFarmCode = typeof route.query.farm_code === 'string' ? route.query.farm_code : ''
      const routeReportType = typeof route.query.report_type === 'string' ? route.query.report_type : ''
      if (routeReportType && REPORT_TYPE_LABELS[routeReportType]) {
        reportType.value = routeReportType
      }

      try {
        await loadFarms()
        if (routeFarmCode && farms.value.some((item) => item.value === routeFarmCode)) {
          station.value = routeFarmCode
        }
        await loadConfigs()
        if (selectedConfigId.value) {
          await loadPreviewData()
        }
      } catch (error) {
        console.error('初始化人工修正工作台失败:', error)
        errorMessage.value = error.response?.data?.error || '初始化人工修正工作台失败'
        ElMessage.error(errorMessage.value)
      }
    })

    return {
      station,
      targetDate,
      reportType,
      tool,
      toolValue,
      capValue,
      farms,
      reportTypeOptions,
      availableConfigs,
      selectedConfigId,
      currentConfig,
      loading,
      saving,
      errorMessage,
      originalRows,
      points,
      previewMeta,
      linePoints,
      baselinePoints,
      toY,
      buildConfigLabel,
      formatNumber,
      getReportTypeName,
      updatePointValue,
      applyTool,
      resetSeries,
      saveVersion,
      loadPreviewData,
      handleStationChange,
      handleReportTypeChange
    }
  }
}
</script>

<style scoped>
.workspace {
  min-height: 100%;
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}

.header h2 {
  margin: 0;
  color: var(--text-primary);
}

.header p {
  margin: 8px 0 0;
  color: var(--text-secondary);
}

.layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 12px;
}

.side,
.chart-card,
.table-card {
  background: rgba(6, 21, 34, 0.86);
  border: 1px solid rgba(130, 178, 212, 0.2);
}

.config-meta {
  display: grid;
  gap: 8px;
  margin-bottom: 12px;
  padding: 10px;
  border-radius: 10px;
  background: rgba(8, 32, 48, 0.55);
}

.meta-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
}

.meta-label {
  color: var(--text-secondary);
}

.meta-value {
  color: var(--text-primary);
  text-align: right;
}

.actions {
  display: grid;
  gap: 8px;
}

.content {
  display: grid;
  gap: 12px;
}

.content-alert {
  margin-bottom: 0;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 10px;
}

.chart-title,
.table-title {
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 600;
}

.chart-tip {
  margin-top: 6px;
  color: var(--text-secondary);
  font-size: 12px;
}

.chart {
  width: 100%;
  height: 420px;
  border-radius: 10px;
  background: rgba(8, 32, 48, 0.55);
  border: 1px solid rgba(130, 178, 212, 0.2);
}

@media (max-width: 1100px) {
  .layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .header,
  .chart-header {
    flex-direction: column;
  }
}
</style>
