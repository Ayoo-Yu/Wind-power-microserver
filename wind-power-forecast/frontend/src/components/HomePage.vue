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

    <div class="dashboard-body">
      <div class="col-left">
        <div class="kpi-row">
          <KpiCards :items="cards" />
        </div>
        <div class="panel-card panel-matrix">
          <div class="panel-title">多场站预测任务监控矩阵</div>
          <FleetMap v-if="topologyPoints.length" :points="topologyPoints" />
          <div v-else-if="!loading" class="empty-state">暂无监控数据</div>
        </div>
      </div>

      <div class="col-right">
        <div class="panel-card panel-trend">
          <div class="panel-title trend-legend">
            日功率预测
            <span class="legend-line" style="background:#2dd4bf"></span>实绩
            <span class="legend-line ll-dash" style="background:#60a5fa"></span>短期
            <span class="legend-line ll-dot" style="background:#fbbf24"></span>超短期
            <span class="legend-line" style="background:#a78bfa"></span>容量
          </div>
          <PowerTrendChart v-if="trendPoints.length" :points="trendPoints" />
          <div v-else-if="!loading" class="empty-state">暂无功率预测数据</div>
        </div>

        <div class="right-bottom">
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

/* ---- 2-column body ---- */
.dashboard-body {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 1fr 2.2fr;
  gap: 12px;
}

.col-left {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
  overflow-y: auto;
}

.col-right {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}

.kpi-row {
  /* KpiCards handles its own grid internally */
}

.panel-matrix {
  flex-shrink: 0;
}

.panel-trend {
  flex: 1.6;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: visible !important;
}

.right-bottom {
  flex: 1;
  min-height: 0;
}

.panel-weather {
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  justify-content: center;
}

/* ---- panel-card ---- */
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
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
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

.wind-icon-sm::before {
  width: 2px;
  height: 14px;
  left: 6px;
  top: 0;
}

.wind-icon-sm::after {
  width: 10px;
  height: 2px;
  left: 2px;
  top: 4px;
}

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

.metric-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.metric-label {
  font-size: 11px;
  color: #9fc4df;
  white-space: nowrap;
}

.metric-value {
  font-size: 16px;
  font-family: Consolas, Menlo, Monaco, monospace;
  color: #dff3ff;
  white-space: nowrap;
}

.metric-value small {
  font-size: 11px;
  color: #8fb2ca;
  margin-left: 2px;
}

/* ---- animations ---- */
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

.empty-state {
  text-align: center;
  color: var(--text-muted);
  padding: 20px 16px;
  font-size: 13px;
}

/* ---- responsive ---- */
@media (max-width: 1280px) {
  .dashboard-body {
    grid-template-columns: 1fr;
    overflow-y: auto;
  }

  .col-left,
  .col-right {
    overflow-y: visible;
  }

  .panel-trend {
    flex: none;
    height: 320px;
  }

  .right-bottom {
    grid-template-columns: 1fr;
  }

  .home-dashboard {
    height: auto;
    overflow: auto;
  }
}

@media (max-width: 720px) {
  .kpi-row {
    grid-template-columns: 1fr;
  }

  .weather-metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .panel-weather {
    justify-content: flex-start;
  }
}
</style>
