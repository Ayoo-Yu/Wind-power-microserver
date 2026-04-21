<template>
  <div class="workspace page-shell">
    <div class="header">
      <div>
        <h2>人工修正工作台</h2>
        <p>基于上报配置预览数据进行人工修正、版本保存、版本比对和手工上报。</p>
      </div>
      <el-tag type="warning" effect="dark">
        数据源：report/configs + preview-report + manual-intervention/versions + manual-report
      </el-tag>
    </div>

    <div class="layout">
      <el-card class="side">
        <el-form label-width="96px">
          <el-form-item label="场站">
            <el-select v-model="station" filterable placeholder="请选择场站" @change="handleStationChange">
              <el-option
                v-for="item in farms"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="目标日期">
            <el-date-picker v-model="targetDate" type="date" value-format="YYYY-MM-DD" @change="handleDateChange" />
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
          <el-form-item label="配置">
            <el-select v-model="selectedConfigId" filterable placeholder="请选择配置">
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
              <el-option label="整体放大(%)" value="scaleUp" />
              <el-option label="整体平移(MW)" value="shift" />
              <el-option label="上限截断(MW)" value="cap" />
            </el-select>
          </el-form-item>
          <el-form-item label="修正值">
            <el-input-number v-model="toolValue" :min="-1000" :max="1000" />
          </el-form-item>
          <el-form-item label="版本名">
            <el-input v-model="versionName" placeholder="可选，默认自动生成" />
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
            <span class="meta-label">工作区点数</span>
            <span class="meta-value">{{ points.length }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">历史版本</span>
            <span class="meta-value">{{ versions.length }}</span>
          </div>
        </div>

        <div class="actions">
          <el-button type="primary" :loading="loading" @click="loadPreviewData">加载预览</el-button>
          <el-button :disabled="points.length === 0" @click="applyTool">应用工具</el-button>
          <el-button :disabled="originalRows.length === 0" @click="resetSeries">重置到原始值</el-button>
          <el-button
            type="warning"
            :disabled="points.length === 0 || !selectedConfigId"
            :loading="versionSaving"
            @click="saveVersion"
          >
            保存版本
          </el-button>
          <el-button
            type="success"
            :disabled="points.length === 0 || !selectedConfigId"
            :loading="submitting"
            @click="submitManualReport"
          >
            提交上报
          </el-button>
        </div>

        <div class="version-panel">
          <div class="panel-title">版本列表</div>
          <el-table :data="versions" size="small" border empty-text="暂无版本">
            <el-table-column prop="versionName" label="版本" min-width="140" show-overflow-tooltip />
            <el-table-column prop="createdAt" label="创建时间" min-width="150" />
            <el-table-column label="操作" width="200">
              <template #default="{ row }">
                <el-button type="primary" link @click="compareVersion(row.id)">对比</el-button>
                <el-button type="warning" link @click="rollbackToVersion(row.id)">回滚</el-button>
              </template>
            </el-table-column>
          </el-table>
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
                虚线为原始值，实线为当前工作区值；上方卡片可直接看到版本数量和当前配置。
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
          <el-empty v-else description="请先加载预览数据" />
        </el-card>

        <el-card class="table-card">
          <div class="table-title">修正点明细</div>
          <el-table :data="points" border stripe empty-text="暂无修正点">
            <el-table-column prop="label" label="点位" min-width="140" />
            <el-table-column prop="sourceValue" label="原始值" width="120">
              <template #default="{ row }">{{ formatNumber(row.sourceValue) }}</template>
            </el-table-column>
            <el-table-column label="修正后值" width="180">
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
            <el-table-column prop="time" label="时间" min-width="180" show-overflow-tooltip />
          </el-table>
        </el-card>

        <el-card v-if="comparedVersion" class="table-card">
          <div class="table-title">版本对比</div>
          <div class="compare-summary">
            <div class="meta-item">
              <span class="meta-label">对比版本</span>
              <span class="meta-value">{{ comparedVersion.versionName }}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">差异点数</span>
              <span class="meta-value">{{ compareSummary.changedCount }}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">最大偏差</span>
              <span class="meta-value">{{ formatNumber(compareSummary.maxDelta) }}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">平均偏差</span>
              <span class="meta-value">{{ formatNumber(compareSummary.avgDelta) }}</span>
            </div>
          </div>
          <el-table :data="compareRows" border stripe size="small" empty-text="无差异">
            <el-table-column prop="label" label="点位" min-width="120" />
            <el-table-column prop="currentValue" label="当前值" width="120">
              <template #default="{ row }">{{ formatNumber(row.currentValue) }}</template>
            </el-table-column>
            <el-table-column prop="versionValue" label="版本值" width="120">
              <template #default="{ row }">{{ formatNumber(row.versionValue) }}</template>
            </el-table-column>
            <el-table-column prop="delta" label="偏差" width="120">
              <template #default="{ row }">
                <span :class="{ 'delta-positive': row.delta > 0, 'delta-negative': row.delta < 0 }">
                  {{ formatNumber(row.delta) }}
                </span>
              </template>
            </el-table-column>
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
import {
  applyManualInterventionVersion,
  createManualInterventionVersion,
  getManualInterventionVersion,
  getManualInterventionVersions,
  getReportConfigs,
  getReportFarms,
  manualReport,
  previewReport
} from '../api/reportApi'
import { getStoredUser, hasAnyPermission } from '../utils/permission'

const REPORT_TYPE_OPTIONS = [
  { value: 'forecast_long', label: '中期预测' },
  { value: 'forecast_short', label: '短期预测' },
  { value: 'actual', label: '实测数据' }
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
  return `加载时间：${new Date().toLocaleString('zh-CN')}`
}

function safeArray(value) {
  return Array.isArray(value) ? value : []
}

function toDisplayTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('zh-CN', { hour12: false })
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
    const versionName = ref('')
    const capValue = ref(null)
    const farms = ref([])
    const configs = ref([])
    const versions = ref([])
    const selectedConfigId = ref(null)
    const loading = ref(false)
    const versionSaving = ref(false)
    const submitting = ref(false)
    const errorMessage = ref('')
    const originalRows = ref([])
    const points = ref([])
    const previewMeta = ref({ loadedAt: '', sourceType: '' })
    const comparedVersion = ref(null)
    const compareRows = ref([])

    const reportTypeOptions = REPORT_TYPE_OPTIONS

    const getReportTypeName = (type) => REPORT_TYPE_LABELS[type] || type || '--'

    const availableConfigs = computed(() => configs.value.filter((item) => item.report_type === reportType.value))

    const currentConfig = computed(() => {
      return availableConfigs.value.find((item) => String(item.id) === String(selectedConfigId.value)) || null
    })

    const compareSummary = computed(() => {
      if (!compareRows.value.length) {
        return { changedCount: 0, maxDelta: 0, avgDelta: 0 }
      }
      const deltas = compareRows.value.map((item) => Math.abs(Number(item.delta || 0)))
      return {
        changedCount: compareRows.value.length,
        maxDelta: Math.max(...deltas, 0),
        avgDelta: deltas.reduce((sum, value) => sum + value, 0) / compareRows.value.length
      }
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

    const canSaveManual = () => hasAnyPermission(getStoredUser(), ['manual_intervention_workspace', 'manage_reports', 'auto_predictions'])

    const buildConfigLabel = (config) => {
      const name = config?.config_name || config?.target_name || `配置${config?.id || ''}`
      return `${name} / ${getReportTypeName(config?.report_type)}`
    }

    const normalizePointSeries = (type, payloadRows, dateText) => {
      const rows = safeArray(payloadRows)

      if (type === 'forecast_short') {
        const row = rows[0] || {}
        const keys = Object.keys(row)
          .filter((key) => /^wp_pred\d+$/.test(key))
          .sort((a, b) => Number(a.replace('wp_pred', '')) - Number(b.replace('wp_pred', '')))
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

    const fillWorkspaceFromPayload = (payloadRows, loadedLabel = buildNowLabel()) => {
      originalRows.value = safeArray(payloadRows)
      points.value = normalizePointSeries(reportType.value, payloadRows, targetDate.value)
      previewMeta.value = {
        loadedAt: loadedLabel,
        sourceType: reportType.value
      }
    }

    const clearCompareState = () => {
      comparedVersion.value = null
      compareRows.value = []
    }

    const applyTool = () => {
      if (points.value.length === 0) {
        ElMessage.warning('请先加载预览数据')
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
      clearCompareState()
    }

    const resetSeries = () => {
      capValue.value = null
      points.value = normalizePointSeries(reportType.value, originalRows.value, targetDate.value)
      clearCompareState()
    }

    const updatePointValue = (index, value) => {
      points.value[index] = {
        ...points.value[index],
        value: Number(value || 0)
      }
      points.value = [...points.value]
      clearCompareState()
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

    const loadVersions = async () => {
      if (!station.value) {
        versions.value = []
        return
      }
      const response = await getManualInterventionVersions({
        farm_code: station.value,
        report_type: reportType.value,
        target_date: targetDate.value
      })
      versions.value = safeArray(response.data).map((item) => ({
        id: item.id,
        versionName: item.version_name || `版本 ${item.id}`,
        createdAt: toDisplayTime(item.created_at),
        raw: item
      }))
    }

    const loadPreviewData = async () => {
      if (!selectedConfigId.value) {
        ElMessage.warning('请先选择配置')
        return
      }

      loading.value = true
      errorMessage.value = ''
      clearCompareState()
      try {
        const response = await previewReport(selectedConfigId.value)
        const payloadRows = safeArray(response.data?.payload?.data)
        fillWorkspaceFromPayload(payloadRows)

        if (points.value.length === 0) {
          errorMessage.value = '当前配置没有返回可编辑数据'
          ElMessage.warning(errorMessage.value)
        } else {
          ElMessage.success(`已加载 ${points.value.length} 个修正点`)
        }
      } catch (error) {
        console.error('load manual preview failed:', error)
        originalRows.value = []
        points.value = []
        previewMeta.value = { loadedAt: '', sourceType: '' }
        errorMessage.value = error.response?.data?.error || '加载预览数据失败'
        ElMessage.error(errorMessage.value)
      } finally {
        loading.value = false
      }
    }

    const saveVersion = async () => {
      if (!canSaveManual()) {
        ElMessage.warning('当前账号没有保存人工修正版本的权限')
        return
      }
      if (!selectedConfigId.value || points.value.length === 0) {
        ElMessage.warning('请先准备好修正数据')
        return
      }

      versionSaving.value = true
      try {
        const currentUser = getStoredUser() || {}
        const response = await createManualInterventionVersion({
          config_id: selectedConfigId.value,
          farm_code: station.value,
          report_type: reportType.value,
          target_date: targetDate.value,
          version_name: versionName.value || '',
          tool_name: tool.value,
          tool_value: toolValue.value,
          created_by: currentUser.username || 'unknown',
          data: denormalizePayload()
        })
        versionName.value = ''
        await loadVersions()
        ElMessage.success(response.data?.message || '版本保存成功')
      } catch (error) {
        console.error('save manual version failed:', error)
        ElMessage.error(error.response?.data?.error || '版本保存失败')
      } finally {
        versionSaving.value = false
      }
    }

    const submitManualReport = async () => {
      if (!canSaveManual()) {
        ElMessage.warning('当前账号没有人工上报权限')
        return
      }
      if (!selectedConfigId.value || points.value.length === 0) {
        ElMessage.warning('请先准备好修正数据')
        return
      }

      submitting.value = true
      try {
        const payload = {
          config_id: selectedConfigId.value,
          data: denormalizePayload()
        }
        await manualReport(payload)
        ElMessage.success(`已提交 ${station.value} ${targetDate.value} 的人工上报`)
      } catch (error) {
        console.error('submit manual report failed:', error)
        ElMessage.error(error.response?.data?.error || '人工上报失败')
      } finally {
        submitting.value = false
      }
    }

    const loadVersion = async (versionId) => {
      try {
        const currentUser = getStoredUser() || {}
        const response = await applyManualInterventionVersion(versionId, {
          applied_by: currentUser.username || 'unknown'
        })
        const version = response.data?.version
        if (!version) {
          ElMessage.warning('版本不存在')
          return
        }
        fillWorkspaceFromPayload(version.payload || [], `版本 ${version.version_name || version.id} 已应用`)
        clearCompareState()
        ElMessage.success(response.data?.message || '版本应用成功')
        await loadVersions()
      } catch (error) {
        console.error('apply manual version failed:', error)
        ElMessage.error(error.response?.data?.error || '版本应用失败')
      }
    }

    const compareVersion = async (versionId) => {
      if (!points.value.length) {
        ElMessage.warning('请先加载当前工作区数据')
        return
      }
      try {
        const response = await getManualInterventionVersion(versionId)
        const version = response.data || response.data?.data
        const payloadRows = safeArray(version?.payload || [])
        const versionPoints = normalizePointSeries(reportType.value, payloadRows, targetDate.value)
        const currentMap = new Map(points.value.map((item) => [item.key, item]))
        compareRows.value = versionPoints
          .map((item) => {
            const current = currentMap.get(item.key)
            if (!current) return null
            const delta = Number((Number(current.value || 0) - Number(item.value || 0)).toFixed(2))
            if (Math.abs(delta) < 0.01) return null
            return {
              key: item.key,
              label: item.label,
              currentValue: Number(current.value || 0),
              versionValue: Number(item.value || 0),
              delta
            }
          })
          .filter(Boolean)
        comparedVersion.value = {
          id: version?.id || versionId,
          versionName: version?.version_name || `版本 ${versionId}`
        }
        if (!compareRows.value.length) {
          ElMessage.info('当前工作区与所选版本一致')
        }
      } catch (error) {
        console.error('compare manual version failed:', error)
        ElMessage.error(error.response?.data?.error || '版本比对失败')
      }
    }

    const rollbackToVersion = async (versionId) => {
      await loadVersion(versionId)
    }

    const handleStationChange = async () => {
      await loadConfigs()
      await loadVersions()
      points.value = []
      originalRows.value = []
      errorMessage.value = ''
      clearCompareState()
    }

    const handleReportTypeChange = async () => {
      selectedConfigId.value = availableConfigs.value[0]?.id || null
      points.value = []
      originalRows.value = []
      errorMessage.value = ''
      clearCompareState()
      await loadVersions()
    }

    const handleDateChange = async () => {
      clearCompareState()
      await loadVersions()
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
        await loadVersions()
        if (selectedConfigId.value) {
          await loadPreviewData()
        }
      } catch (error) {
        console.error('init manual workspace failed:', error)
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
      versionName,
      capValue,
      farms,
      versions,
      reportTypeOptions,
      availableConfigs,
      selectedConfigId,
      currentConfig,
      loading,
      versionSaving,
      submitting,
      errorMessage,
      originalRows,
      points,
      previewMeta,
      comparedVersion,
      compareRows,
      compareSummary,
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
      submitManualReport,
      loadVersion,
      compareVersion,
      rollbackToVersion,
      loadPreviewData,
      handleStationChange,
      handleReportTypeChange,
      handleDateChange
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
  grid-template-columns: 360px 1fr;
  gap: 12px;
}

.side,
.chart-card,
.table-card {
  background: var(--gradient-card);
  border: 1px solid var(--border-color);
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

.version-panel {
  margin-top: 14px;
}

.panel-title {
  margin-bottom: 10px;
  color: var(--text-primary);
  font-weight: 600;
}

.content {
  display: grid;
  gap: 12px;
}

.compare-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
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
  height: 360px;
}

.delta-positive {
  color: #fca5a5;
}

.delta-negative {
  color: #86efac;
}

@media (max-width: 1200px) {
  .layout {
    grid-template-columns: 1fr;
  }

  .compare-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
