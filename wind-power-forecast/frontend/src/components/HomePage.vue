<template>
  <div class="page-shell home-dashboard">
    <div class="dashboard-head panel-card">
      <div class="title-wrap">
        <h1>风电预测业务总览</h1>
        <div class="title-meta">
          <span class="title-dot"></span>
          <span class="title-time">更新时间: {{ updatedAt }}</span>
        </div>
      </div>
      <el-button class="refresh-btn" :loading="loading" @click="loadData">
        <el-icon><Refresh /></el-icon>
      </el-button>
    </div>

    <div class="kpi-section">
      <KpiCards :items="cards" />
    </div>

    <div class="dashboard-body">
      <div class="panel-card panel-trend">
        <div class="panel-title trend-legend">
          日功率预测
          <span class="legend-line legend-actual"></span>实绩
          <span class="legend-line legend-short ll-dash"></span>短期
          <span class="legend-line legend-ultra ll-dot"></span>超短期
          <span class="legend-line legend-capacity"></span>容量
        </div>
        <PowerTrendChart v-if="trendPoints.length" :points="trendPoints" @range-change="onRangeChange" />
        <div v-else-if="!loading" class="empty-state">暂无功率预测数据</div>
      </div>

      <div class="col-right">
        <div class="panel-card panel-weather">
          <div class="panel-title">
            气象概览
            <span v-if="weatherUpdateTime" class="weather-update-hint">NWP更新: {{ weatherUpdateTime.slice(11, 16) }}</span>
          </div>

          <div v-if="weatherMetrics.length" class="weather-metrics-grid">
            <div v-for="item in weatherMetrics" :key="item.label" class="weather-metric-item">
              <div class="metric-info">
                <div class="metric-label">{{ item.label }}</div>
                <div class="metric-value">{{ item.value }} <small>{{ item.unit }}</small></div>
              </div>
            </div>
          </div>
          <div v-else-if="!loading" class="empty-state">暂无气象数据</div>
        </div>

        <div class="panel-card panel-matrix">
          <div class="panel-title">多场站预测任务监控矩阵</div>
          <FleetMap v-if="topologyPoints.length" :points="topologyPoints" />
          <div v-else-if="!loading" class="empty-state">暂无监控数据</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import farmService from '@/utils/farmService'
import {
  getDashboardOverview,
  getDashboardTrend,
  getDashboardWeatherSnapshot
} from '@/services/dashboardService'

import KpiCards from '@/components/dashboard/KpiCards.vue'
import FleetMap from '@/components/dashboard/FleetMap.vue'
import PowerTrendChart from '@/components/dashboard/PowerTrendChart.vue'

const loading = ref(false)
const cards = ref([])
const topologyPoints = ref([])
const trendPoints = ref([])
const weatherMetrics = ref([])
const weatherUpdateTime = ref(null)
const updatedAt = ref('--')

let farmListener = null

function formatNow() {
  const d = new Date()
  const y = d.getFullYear()
  const m = `${d.getMonth() + 1}`.padStart(2, '0')
  const day = `${d.getDate()}`.padStart(2, '0')
  const h = `${d.getHours()}`.padStart(2, '0')
  const mi = `${d.getMinutes()}`.padStart(2, '0')
  const s = `${d.getSeconds()}`.padStart(2, '0')
  return `${y}-${m}-${day} ${h}:${mi}:${s}`
}

const activeRange = ref('1d')

function getRangeDates(range) {
  const now = new Date()
  const end = new Date(now)
  end.setHours(23, 59, 59, 999)
  const start = new Date(now)
  start.setHours(0, 0, 0, 0)
  if (range === '3d') start.setDate(start.getDate() - 2)
  if (range === '7d') start.setDate(start.getDate() - 6)

  const fmt = (d) => {
    const y = d.getFullYear()
    const m = `${d.getMonth() + 1}`.padStart(2, '0')
    const day = `${d.getDate()}`.padStart(2, '0')
    const hh = `${d.getHours()}`.padStart(2, '0')
    const mm = `${d.getMinutes()}`.padStart(2, '0')
    const ss = `${d.getSeconds()}`.padStart(2, '0')
    return `${y}-${m}-${day} ${hh}:${mm}:${ss}`
  }
  return { start: fmt(start), end: fmt(end) }
}

async function onRangeChange(range) {
  activeRange.value = range
  loading.value = true
  const farmCode = farmService.getCurrentFarm()
  const rangeDates = getRangeDates(range)
  try {
    const trend = await getDashboardTrend({
      farmCode,
      start: rangeDates.start,
      end: rangeDates.end
    })
    trendPoints.value = trend || []
  } catch (error) {
    console.warn('趋势数据加载失败:', error?.message || error)
  } finally {
    loading.value = false
  }
}

async function loadData() {
  loading.value = true
  const farmCode = farmService.getCurrentFarm()
  try {
    const [overview, trend, weather] = await Promise.all([
      getDashboardOverview({ farmCode }),
      getDashboardTrend({ farmCode }),
      getDashboardWeatherSnapshot({ farmCode })
    ])

    cards.value = overview.cards || []
    topologyPoints.value = overview.topology || []
    trendPoints.value = trend || []
    weatherMetrics.value = weather?.metrics || []
    weatherUpdateTime.value = weather?.updateTime || null
    updatedAt.value = formatNow()
  } catch (error) {
    console.warn('首页数据加载失败:', error?.message || error)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await farmService.loadAvailableFarms()
  await loadData()

  farmListener = async () => {
    await loadData()
  }
  farmService.addListener(farmListener)
})

onBeforeUnmount(() => {
  if (farmListener) {
    farmService.removeListener(farmListener)
    farmListener = null
  }
})
</script>

<style scoped>
.home-dashboard {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 72px);
  overflow: hidden;
}

.dashboard-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 20px;
  flex-shrink: 0;
}

.dashboard-head h1 {
  margin: 0;
  color: var(--text-primary);
  font-size: 23px;
  font-weight: 650;
  letter-spacing: -0.02em;
}

.title-wrap {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.title-meta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.title-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--success);
}

.title-time {
  font-size: 12px;
  color: var(--text-muted);
}

.refresh-btn {
  border: 1px solid var(--border-color) !important;
  background: var(--surface) !important;
  color: var(--text-secondary) !important;
  border-radius: 10px !important;
  padding: 9px !important;
  transition: all 0.2s ease;
}

.refresh-btn:hover {
  border-color: var(--primary) !important;
  color: var(--primary) !important;
  background: var(--primary-soft) !important;
}

.kpi-section {
  flex-shrink: 0;
  padding: 0 0 2px 0;
}

.dashboard-body {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 16px;
}

.col-right {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
}

.panel-trend {
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.panel-weather {
  flex: 2;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-matrix {
  flex: 3;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-card {
  position: relative;
  padding: 20px;
  overflow: hidden;
  box-shadow: var(--shadow-card);
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 14px;
  flex-shrink: 0;
}

.legend-line {
  display: inline-block;
  width: 16px;
  height: 0;
  vertical-align: middle;
  margin: 0 3px 0 6px;
  border-top: 2px solid currentColor;
}

.ll-dash {
  border-top-style: dashed;
}

.ll-dot {
  border-top-style: dotted;
}

.legend-actual { color: #247a52; }
.legend-short { color: #397b91; }
.legend-ultra { color: #b7791f; }
.legend-capacity { color: #7c6f9b; }

.weather-update-hint {
  margin-left: 12px;
  font-size: 12px;
  font-weight: 400;
  color: var(--text-muted);
}

.weather-metrics-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  flex: 1;
  align-content: start;
}

.weather-metric-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 12px;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background: var(--surface-soft);
  overflow: hidden;
}

.weather-metric-item:last-child:nth-child(odd) {
  grid-column: 1 / -1;
  max-width: 50%;
  justify-self: center;
}

.metric-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}
.metric-label { font-size: 11px; color: var(--text-muted); white-space: nowrap; }
.metric-value {
  font-size: 16px;
  font-family: var(--font-mono);
  color: var(--text-primary);
  font-weight: 600;
  white-space: nowrap;
}
.metric-value small { font-size: 11px; color: var(--text-muted); margin-left: 2px; font-weight: 400; }

.empty-state {
  text-align: center;
  color: var(--text-muted);
  padding: 20px 16px;
  font-size: 13px;
}

@media (max-width: 1280px) {
  .dashboard-body {
    grid-template-columns: 1fr;
    overflow-y: auto;
  }
  .panel-trend {
    flex: none;
    height: 320px;
  }
  .home-dashboard {
    height: auto;
    overflow: auto;
  }
}

@media (max-width: 720px) {
  .weather-metrics-grid {
    grid-template-columns: 1fr;
  }
  .weather-metric-item:last-child:nth-child(odd) {
    max-width: 100%;
  }
}
</style>
