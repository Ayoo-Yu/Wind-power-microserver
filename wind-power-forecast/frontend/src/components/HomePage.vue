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
          <span class="legend-line" style="background:#2dd4bf"></span>实绩
          <span class="legend-line ll-dash" style="background:#60a5fa"></span>短期
          <span class="legend-line ll-dot" style="background:#fbbf24"></span>超短期
          <span class="legend-line" style="background:#a78bfa"></span>容量
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
              <div class="metric-icon" :class="`metric-${item.icon}`">
                <i v-if="item.icon === 'wind'" class="wind-icon-sm"></i>
                <i v-else-if="item.icon === 'compass'" class="compass-icon-sm"></i>
                <i v-else-if="item.icon === 'temp'" class="temp-icon-sm"></i>
                <i v-else-if="item.icon === 'pressure'" class="pressure-icon-sm"></i>
                <i v-else class="drop-icon-sm"></i>
              </div>
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

const DEMO_WEATHER = [
  { label: '轮毂高度风速', value: '6.8', unit: 'm/s', icon: 'wind' },
  { label: '地面风速', value: '4.2', unit: 'm/s', icon: 'wind' },
  { label: '主导风向', value: '西北', unit: '315°', icon: 'compass' },
  { label: '气温', value: '18.5', unit: '°C', icon: 'temp' },
  { label: '湿度', value: '62', unit: '%', icon: 'drop' },
  { label: '气压', value: '1013', unit: 'hPa', icon: 'pressure' },
]
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
    weatherMetrics.value = weather?.metrics?.length ? weather.metrics : DEMO_WEATHER
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
  height: calc(100vh - 64px);
  overflow: hidden;
}

/* ---- header ---- */
.dashboard-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  flex-shrink: 0;
}

.dashboard-head h1 {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 0.5px;
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
  background: #2dd36f;
  box-shadow: 0 0 8px rgba(45, 211, 111, 0.6);
}

.title-time {
  font-size: 12px;
  color: var(--text-muted);
}

.refresh-btn {
  border: 1px solid rgba(146, 186, 220, 0.3) !important;
  background: transparent !important;
  color: var(--text-secondary) !important;
  border-radius: 8px !important;
  padding: 8px !important;
  transition: all 0.2s ease;
}

.refresh-btn:hover {
  border-color: rgba(18, 215, 255, 0.5) !important;
  color: var(--accent) !important;
  background: rgba(18, 215, 255, 0.06) !important;
}

/* ---- KPI section ---- */
.kpi-section {
  flex-shrink: 0;
  padding: 0 0 2px 0;
}

/* ---- main body: trend (left) + right sidebar ---- */
.dashboard-body {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 12px;
}

.col-right {
  display: flex;
  flex-direction: column;
  gap: 12px;
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

/* ---- panel-card base ---- */
.panel-card {
  position: relative;
  padding: 14px;
  overflow: hidden;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
}

.panel-card::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(18, 215, 255, 0.15), transparent);
  pointer-events: none;
}

.panel-title {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 8px;
  flex-shrink: 0;
}

/* ---- trend legend ---- */
.legend-line {
  display: inline-block;
  width: 16px;
  height: 2px;
  vertical-align: middle;
  margin: 0 3px 0 6px;
  border-radius: 1px;
}

.ll-dash {
  background: repeating-linear-gradient(90deg, currentColor 0 4px, transparent 4px 7px) !important;
}

.ll-dot {
  background: repeating-linear-gradient(90deg, currentColor 0 2px, transparent 2px 4px) !important;
}

/* ---- weather ---- */
.weather-update-hint {
  margin-left: 12px;
  font-size: 12px;
  color: #7ca8c4;
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
  gap: 6px;
  padding: 8px;
  border: 1px solid rgba(136, 186, 217, 0.12);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.025);
  overflow: hidden;
}

.weather-metric-item:last-child:nth-child(odd) {
  grid-column: 1 / -1;
  max-width: 50%;
  justify-self: center;
}

.metric-icon {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.metric-wind { background: rgba(18, 215, 255, 0.12); }
.metric-compass { background: rgba(45, 211, 111, 0.12); }
.metric-temp { background: rgba(255, 125, 69, 0.12); }
.metric-drop { background: rgba(100, 160, 255, 0.12); }
.metric-pressure { background: rgba(167, 200, 220, 0.12); }

.wind-icon-sm {
  width: 14px;
  height: 14px;
  display: inline-block;
  position: relative;
}
.wind-icon-sm::before,
.wind-icon-sm::after {
  content: '';
  position: absolute;
  background: #5de0ff;
  border-radius: 1px;
}
.wind-icon-sm::before { width: 2px; height: 14px; left: 6px; top: 0; }
.wind-icon-sm::after { width: 10px; height: 2px; left: 2px; top: 4px; }

.compass-icon-sm {
  width: 12px;
  height: 12px;
  border: 2px solid #2dd36f;
  border-radius: 50%;
  display: inline-block;
  position: relative;
}
.compass-icon-sm::after {
  content: '';
  position: absolute;
  top: 1px;
  left: 3px;
  width: 0;
  height: 0;
  border-left: 3px solid transparent;
  border-right: 3px solid transparent;
  border-bottom: 5px solid #2dd36f;
}

.temp-icon-sm, .drop-icon-sm {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: inline-block;
}
.temp-icon-sm { background: #ff7d45; }
.drop-icon-sm {
  display: inline-block !important;
  width: 12px !important;
  height: 12px !important;
  background: radial-gradient(circle at 40% 35%, #8ec5ff, #5a9ef5);
  border-radius: 50%;
}

.pressure-icon-sm {
  width: 14px;
  height: 12px;
  display: inline-block;
  position: relative;
}
.pressure-icon-sm::before {
  content: '';
  position: absolute;
  left: 0;
  top: 3px;
  width: 14px;
  height: 2px;
  background: #a7c8dc;
  border-radius: 1px;
}
.pressure-icon-sm::after {
  content: '';
  position: absolute;
  left: 0;
  top: 7px;
  width: 14px;
  height: 6px;
  border: 2px solid #a7c8dc;
  border-top: none;
  border-radius: 0 0 3px 3px;
}

.metric-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}
.metric-label { font-size: 11px; color: #9fc4df; white-space: nowrap; }
.metric-value {
  font-size: 16px;
  font-family: Consolas, Menlo, Monaco, monospace;
  color: #dff3ff;
  white-space: nowrap;
}
.metric-value small { font-size: 11px; color: #8fb2ca; margin-left: 2px; }

/* ---- empty & animation ---- */
.empty-state {
  text-align: center;
  color: var(--text-muted);
  padding: 20px 16px;
  font-size: 13px;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

/* ---- responsive ---- */
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
