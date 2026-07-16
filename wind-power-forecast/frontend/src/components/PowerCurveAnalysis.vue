<template>
  <div class="power-curve-analysis">
    <div class="page-header">
      <h2>风速功率曲线</h2>
      <p>识别离群、限电与欠发数据，并将确认后的异常写入数据质量标记。</p>
    </div>
    <div class="controls">
      <el-date-picker
        v-model="dateRange"
        type="daterange"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        value-format="YYYY-MM-DD"
        :shortcuts="dateShortcuts"
        @change="loadData"
      />
      <el-checkbox-group v-model="visibleTypes">
        <el-checkbox label="normal">正常点</el-checkbox>
        <el-checkbox label="outlier">离群点</el-checkbox>
        <el-checkbox label="curtailment">限电</el-checkbox>
        <el-checkbox label="underperformance">欠发</el-checkbox>
      </el-checkbox-group>
      <el-button type="primary" @click="loadData" :loading="loading">分析</el-button>
      <el-button type="warning" @click="markAnomalies" :disabled="!hasAnomalies" :loading="marking">
        标记异常到质量系统
      </el-button>
    </div>

    <div class="summary-cards" v-if="summary">
      <el-card shadow="hover">
        <div class="stat-value">{{ summary.total }}</div>
        <div class="stat-label">总数据点</div>
      </el-card>
      <el-card shadow="hover" :class="{ 'alert-card': summary.alertTriggered }">
        <div class="stat-value">{{ (summary.abnormalRate * 100).toFixed(1) }}%</div>
        <div class="stat-label">异常率</div>
      </el-card>
      <el-card shadow="hover">
        <div class="stat-value stat-outlier">{{ summary.outliers }}</div>
        <div class="stat-label">离群点</div>
      </el-card>
      <el-card shadow="hover">
        <div class="stat-value stat-danger">{{ summary.curtailments }}</div>
        <div class="stat-label">限电</div>
      </el-card>
      <el-card shadow="hover">
        <div class="stat-value stat-warning">{{ summary.underperformance }}</div>
        <div class="stat-label">欠发</div>
      </el-card>
    </div>

    <div ref="chartContainer" class="chart-container"></div>
  </div>
</template>

<script>
import { ref, watch, onMounted, onUnmounted, nextTick, computed } from 'vue'
import * as echarts from '../utils/echarts'
import { ElMessage } from 'element-plus'
import {
  fetchPowerCurveData,
  extractWindPowerPairs,
  computeBinStatistics,
  detectAnomalies,
  computeSummary,
  createAnomalyAlert,
} from '../services/powerCurveService'
import farmService from '../utils/farmService'
import { getFarms } from '../api/farmApi'
import axiosInstance from '../api/axios'

export default {
  name: 'PowerCurveAnalysis',
  setup() {
    const chartContainer = ref(null)
    let chart = null

    const dateRange = ref([])
    const loading = ref(false)
    const marking = ref(false)
    const visibleTypes = ref(['normal', 'outlier', 'curtailment', 'underperformance'])
    const allResults = ref([])
    const binStats = ref([])
    const summary = ref(null)
    const farmCapacity = ref(779.0)

    const hasAnomalies = computed(() => {
      return summary.value && summary.value.abnormalCount > 0
    })

    async function resolveCapacity() {
      const farmCode = farmService.getCurrentFarm()
      try {
        const farms = await getFarms()
        const farm = (farms || []).find((f) => f.farm_code === farmCode)
        if (farm && Number(farm.capacity) > 0) {
          farmCapacity.value = Number(farm.capacity)
        }
      } catch {
        // keep default 779.0
      }
    }

    watch(() => farmService.getCurrentFarm(), async () => {
      await resolveCapacity()
      if (dateRange.value && dateRange.value.length === 2) {
        loadData()
      }
    })

    const dateShortcuts = [
      {
        text: '最近 7 天',
        value: () => {
          const end = new Date()
          const start = new Date()
          start.setTime(start.getTime() - 7 * 24 * 3600 * 1000)
          return [start, end]
        },
      },
      {
        text: '最近 30 天',
        value: () => {
          const end = new Date()
          const start = new Date()
          start.setTime(start.getTime() - 30 * 24 * 3600 * 1000)
          return [start, end]
        },
      },
    ]

    let resizeHandler = null

    function initChart() {
      if (chartContainer.value && !chart) {
        chart = echarts.init(chartContainer.value)
        resizeHandler = () => chart?.resize()
        window.addEventListener('resize', resizeHandler)
      }
    }

    async function loadData() {
      if (!dateRange.value || dateRange.value.length < 2) return
      loading.value = true
      try {
        const rawData = await fetchPowerCurveData(dateRange.value[0], dateRange.value[1])
        const points = extractWindPowerPairs(rawData)
        const stats = computeBinStatistics(points)
        const results = detectAnomalies(points, stats, farmCapacity.value)

        allResults.value = results
        binStats.value = stats
        summary.value = computeSummary(results)

        if (summary.value.alertTriggered) {
          createAnomalyAlert(summary.value, farmService.getCurrentFarm())
        }

        await nextTick()
        renderChart()
      } catch (err) {
        ElMessage.error('加载功率曲线数据失败: ' + (err.message || '未知错误'))
      } finally {
        loading.value = false
      }
    }

    function renderChart() {
      if (!chart) initChart()
      if (!chart) return

      const series = []

      // 置信带
      if (binStats.value.length > 0) {
        const upperData = binStats.value.map((s) => [s.windSpeedCenter, s.upper])
        const lowerData = binStats.value.map((s) => [s.windSpeedCenter, s.lower])
        series.push({
          name: '置信带上界',
          type: 'line',
          data: upperData,
          lineStyle: { opacity: 0 },
          areaStyle: { color: 'rgba(74, 222, 128, 0.12)' },
          stack: 'confidence-band',
          symbol: 'none',
          silent: true,
          z: 1,
        })
        series.push({
          name: '置信带下界',
          type: 'line',
          data: lowerData,
          lineStyle: { opacity: 0 },
          areaStyle: { color: '#1a1a2e' },
          stack: 'confidence-band',
          symbol: 'none',
          silent: true,
          z: 1,
        })
      }

      // 理论功率曲线参考线
      const theoreticalPoints = allResults.value
        .filter((r) => r.theoreticalPower != null && r.theoreticalPower > 0)
        .map((r) => [r.windSpeed, r.theoreticalPower])
      if (theoreticalPoints.length > 20) {
        const sorted = theoreticalPoints.sort((a, b) => a[0] - b[0])
        const step = Math.max(1, Math.floor(sorted.length / 100))
        const sampled = sorted.filter((_, i) => i % step === 0)
        series.push({
          name: '理论功率曲线',
          type: 'line',
          data: sampled,
          lineStyle: { color: '#9ca3af', width: 2, type: 'dashed' },
          symbol: 'none',
          silent: true,
          z: 0,
        })
      }

      // Normal points
      if (visibleTypes.value.includes('normal')) {
        series.push({
          name: '正常点',
          type: 'scatter',
          data: allResults.value.filter((r) => r.type === 'normal').map((r) => [r.windSpeed, r.power]),
          symbolSize: 3,
          itemStyle: { color: '#4ade80', opacity: 0.4 },
          z: 2,
        })
      }

      // Outliers
      if (visibleTypes.value.includes('outlier')) {
        series.push({
          name: '离群点',
          type: 'scatter',
          data: allResults.value.filter((r) => r.type === 'outlier').map((r) => [r.windSpeed, r.power]),
          symbolSize: 6,
          itemStyle: { color: '#a855f7' },
          z: 3,
        })
      }

      // Curtailment
      if (visibleTypes.value.includes('curtailment')) {
        series.push({
          name: '限电',
          type: 'scatter',
          data: allResults.value.filter((r) => r.type === 'curtailment').map((r) => [r.windSpeed, r.power]),
          symbolSize: 6,
          itemStyle: { color: '#ef4444' },
          z: 3,
        })
      }

      // Underperformance
      if (visibleTypes.value.includes('underperformance')) {
        series.push({
          name: '欠发',
          type: 'scatter',
          data: allResults.value.filter((r) => r.type === 'underperformance').map((r) => [r.windSpeed, r.power]),
          symbolSize: 6,
          itemStyle: { color: '#f59e0b' },
          z: 3,
        })
      }

      chart.setOption(
        {
          title: { text: '功率曲线异常检测', left: 'center' },
          tooltip: {
            trigger: 'item',
            formatter: (params) =>
              `${params.seriesName}<br/>风速: ${params.data[0].toFixed(1)} m/s<br/>功率: ${params.data[1].toFixed(1)} MW`,
          },
          legend: { bottom: 10 },
          grid: { left: 60, right: 30, top: 50, bottom: 60 },
          xAxis: { name: '风速 (m/s)', nameLocation: 'center', nameGap: 30, min: 0, max: 25 },
          yAxis: { name: '功率 (MW)', nameLocation: 'center', nameGap: 50, min: 0 },
          series,
        },
        true
      )
    }

    async function markAnomalies() {
      const anomalies = allResults.value.filter(
        (r) => r.type === 'outlier' || r.type === 'curtailment' || r.type === 'underperformance'
      )
      if (anomalies.length === 0) return

      marking.value = true
      try {
        const typeMap = { outlier: '离群点', curtailment: '限电', underperformance: '欠发' }
        const byType = {}
        for (const a of anomalies) {
          const label = typeMap[a.type] || a.type
          if (!byType[label]) byType[label] = []
          byType[label].push(a)
        }

        const requests = Object.entries(byType).map(([label, points]) => {
          const timestamps = points.map((p) => p.timestamp).filter(Boolean).sort()
          if (timestamps.length === 0) return Promise.resolve()
          return axiosInstance.post('/api/v1/report/quality-markers', {
            farm_code: farmService.getCurrentFarm(),
            start_time: timestamps[0],
            end_time: timestamps[timestamps.length - 1],
            marker_type: '功率曲线异常',
            reason: `自动检测: ${label} (${points.length} 个点)`,
            exclude_from_score: true,
          })
        })
        await Promise.all(requests)
        ElMessage.success(`已标记 ${anomalies.length} 个异常点到质量系统`)
      } catch (err) {
        ElMessage.error('标记失败: ' + (err.message || '未知错误'))
      } finally {
        marking.value = false
      }
    }

    onMounted(async () => {
      const end = new Date()
      const start = new Date()
      start.setTime(start.getTime() - 7 * 24 * 3600 * 1000)
      dateRange.value = [start.toISOString().slice(0, 10), end.toISOString().slice(0, 10)]
      await resolveCapacity()
      nextTick(() => {
        initChart()
        loadData()
      })
    })

    onUnmounted(() => {
      if (resizeHandler) {
        window.removeEventListener('resize', resizeHandler)
        resizeHandler = null
      }
      if (chart) {
        chart.dispose()
        chart = null
      }
    })

    return {
      chartContainer,
      dateRange,
      loading,
      marking,
      visibleTypes,
      summary,
      hasAnomalies,
      dateShortcuts,
      loadData,
      markAnomalies,
    }
  },
}
</script>

<style scoped>
.power-curve-analysis {
  padding: 20px;
}

.page-header h2 {
  margin: 0;
  color: var(--text-primary);
}

.page-header p {
  margin: 8px 0 16px;
  color: var(--text-secondary);
}
.controls {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.summary-cards {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}
.summary-cards .el-card {
  flex: 1;
  text-align: center;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
}
.stat-label {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 4px;
}
.stat-outlier { color: #6f5a94; }
.stat-danger { color: #a64343; }
.stat-warning { color: #966019; }
.alert-card {
  border: 2px solid #ef4444 !important;
}
.alert-card .stat-value {
  color: #a64343;
}
.chart-container {
  width: 100%;
  height: 500px;
}
</style>
