<template>
  <div class="page-shell home-dashboard">
    <div class="dashboard-head panel-card">
      <div class="title-wrap">
        <h1>风电预测业务总览</h1>
        <p>更新时间: {{ updatedAt }}</p>
        <div class="title-deco">
          <span class="title-dot"></span>
          <i class="title-line"></i>
        </div>
      </div>
      <el-button type="primary" :loading="loading" @click="loadData">刷新</el-button>
    </div>

    <div class="kpi-row">
      <KpiCards :items="cards" />
      <ExtremeWeatherCard />
    </div>

    <div class="dashboard-grid">
      <div class="panel-card panel-trend">
        <div class="panel-title">日功率预测（实绩 / 短期 / 超短期 / 可用容量）</div>
        <PowerTrendChart v-if="trendPoints.length" :points="trendPoints" />
        <div v-else-if="!loading" class="empty-state">暂无功率预测数据</div>
      </div>

      <div class="panel-card panel-left">
        <div class="panel-title">场站出力排名</div>
        <StationRankChart v-if="rankRows.length" :rows="rankRows" />
        <div v-else-if="!loading" class="empty-state">暂无场站排名数据</div>
      </div>

      <div class="panel-card panel-center">
        <div class="panel-title">多场站预测任务监控矩阵</div>
        <FleetMap v-if="topologyPoints.length" :points="topologyPoints" />
        <div v-else-if="!loading" class="empty-state">暂无监控数据</div>
      </div>
    </div>

    <div class="dashboard-bottom">
      <div class="panel-card weather-card">
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

      <div class="panel-card events-card">
        <div class="panel-title event-title-row">
          <span>实时事件 / 告警</span>
          <div class="event-tabs">
            <button
              v-for="tab in eventTabs"
              :key="tab.key"
              class="event-tab-btn"
              :class="{ active: activeEventTab === tab.key }"
              @click="activeEventTab = tab.key"
            >
              {{ tab.label }}
            </button>
          </div>
        </div>
        <ul class="event-list">
          <li v-for="event in scrollingEvents" :key="event.id" class="event-item">
            <span class="event-time">
              <i class="event-dot" :class="`event-dot-${event.level}`"></i>
              {{ event.time }}
            </span>
            <span class="event-tag" :class="`event-${event.level}`">{{ event.levelText }}</span>
            <span class="event-text">{{ event.message }}</span>
          </li>
        </ul>
        <div v-if="events.length === 0 && !loading" class="empty-state">暂无事件记录</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import farmService from '@/utils/farmService'
import {
  getDashboardOverview,
  getDashboardStationRank,
  getDashboardTrend,
  getDashboardWeatherSnapshot,
  getDashboardEvents
} from '@/services/dashboardService'
import KpiCards from '@/components/dashboard/KpiCards.vue'
import ExtremeWeatherCard from '@/components/ExtremeWeatherCard.vue'
import FleetMap from '@/components/dashboard/FleetMap.vue'
import StationRankChart from '@/components/dashboard/StationRankChart.vue'
import PowerTrendChart from '@/components/dashboard/PowerTrendChart.vue'

const loading = ref(false)
const cards = ref([])
const topologyPoints = ref([])
const rankRows = ref([])
const trendPoints = ref([])
const weatherMetrics = ref([])
const weatherUpdateTime = ref(null)
const events = ref([])
const updatedAt = ref('--')

const eventTabs = [
  { key: 'all', label: '全部' },
  { key: 'system', label: '系统' },
  { key: 'business', label: '业务' }
]
const activeEventTab = ref('all')

let eventTicker = null
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
    const [overview, rank, trend, weather, eventRows] = await Promise.all([
      getDashboardOverview({ farmCode }),
      getDashboardStationRank({ farmCode }),
      getDashboardTrend({ farmCode }),
      getDashboardWeatherSnapshot({ farmCode }),
      getDashboardEvents({ farmCode, limit: 12 })
    ])

    cards.value = overview.cards || []
    topologyPoints.value = overview.topology || []
    rankRows.value = rank || []
    trendPoints.value = trend || []
    weatherMetrics.value = weather?.metrics || []
    weatherUpdateTime.value = weather?.updateTime || null
    events.value = eventRows || []
    updatedAt.value = formatNow()
  } finally {
    loading.value = false
  }
}

const filteredEvents = computed(() => {
  if (activeEventTab.value === 'all') return events.value
  return events.value.filter(event => event.category === activeEventTab.value)
})

const scrollingEvents = computed(() => filteredEvents.value.slice(0, 8))

function startEventTicker() {
  if (eventTicker) clearInterval(eventTicker)
  eventTicker = setInterval(() => {
    if (events.value.length > 1) {
      events.value = [...events.value.slice(1), events.value[0]]
    }
  }, 2600)
}

onMounted(async () => {
  await farmService.loadAvailableFarms()
  await loadData()
  startEventTicker()

  farmListener = async () => {
    await loadData()
  }
  farmService.addListener(farmListener)
})

onBeforeUnmount(() => {
  if (eventTicker) {
    clearInterval(eventTicker)
    eventTicker = null
  }
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
  gap: 12px;
}

.dashboard-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
}

.dashboard-head h1 {
  margin: 0;
  font-size: 22px;
  letter-spacing: 0.5px;
}

.title-wrap {
  display: flex;
  flex-direction: column;
}

.dashboard-head p {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.title-deco {
  margin-top: 8px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.title-dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  background: #12d7ff;
  box-shadow: 0 0 10px rgba(18, 215, 255, 0.6);
}

.title-line {
  width: 180px;
  height: 1px;
  background: linear-gradient(90deg, rgba(18, 215, 255, 0.45), rgba(18, 215, 255, 0));
}

.kpi-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  align-items: start;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: 1fr 1.8fr;
  gap: 12px;
}

.panel-trend {
  grid-column: 1 / 3;
}

.dashboard-bottom {
  display: grid;
  grid-template-columns: 1.15fr 1fr;
  gap: 12px;
}

.panel-card {
  position: relative;
  padding: 12px;
  overflow: hidden;
  box-shadow: 0 10px 22px rgba(7, 20, 33, 0.35), 0 0 14px rgba(18, 215, 255, 0.08);
}

.panel-card::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  box-shadow: inset 0 0 12px rgba(18, 215, 255, 0.08);
}

.panel-title {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 10px;
}

.weather-update-hint {
  margin-left: 12px;
  font-size: 12px;
  color: #7ca8c4;
}

.weather-metrics-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 10px;
}

.weather-metric-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border: 1px solid rgba(136, 186, 217, 0.2);
  border-radius: 10px;
  background: rgba(7, 24, 39, 0.58);
}

.metric-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
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
  width: 16px;
  height: 16px;
  border: 2px solid #5de0ff;
  border-left-color: transparent;
  border-radius: 50%;
  display: inline-block;
  animation: spin 2s linear infinite;
}

.compass-icon-sm {
  width: 14px;
  height: 14px;
  border: 2px solid #2dd36f;
  border-radius: 50%;
  display: inline-block;
  position: relative;
}

.compass-icon-sm::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 4px;
  width: 0;
  height: 0;
  border-left: 3px solid transparent;
  border-right: 3px solid transparent;
  border-bottom: 6px solid #2dd36f;
}

.temp-icon-sm, .drop-icon-sm {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}

.temp-icon-sm { background: #ff7d45; }
.drop-icon-sm { background: #64a0ff; }

.metric-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.metric-label {
  font-size: 12px;
  color: #9fc4df;
  white-space: nowrap;
}

.metric-value {
  font-size: 18px;
  font-family: Consolas, Menlo, Monaco, monospace;
  color: #dff3ff;
  white-space: nowrap;
}

.metric-value small {
  font-size: 12px;
  color: #8fb2ca;
  margin-left: 2px;
}

.event-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.event-tabs {
  display: inline-flex;
  gap: 6px;
}

.event-tab-btn {
  border: 1px solid rgba(136, 186, 217, 0.25);
  background: rgba(7, 24, 39, 0.58);
  color: #8fb2ca;
  border-radius: 999px;
  padding: 3px 10px;
  font-size: 12px;
  cursor: pointer;
}

.event-tab-btn.active {
  color: #dff3ff;
  border-color: rgba(18, 215, 255, 0.5);
  background: rgba(18, 215, 255, 0.12);
}

.event-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 220px;
  overflow: auto;
}

.event-item {
  display: grid;
  grid-template-columns: 86px 52px 1fr;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(7, 24, 39, 0.58);
  border: 1px solid rgba(136, 186, 217, 0.15);
}

.event-time {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #87a7c1;
  font-family: Consolas, Menlo, Monaco, monospace;
  font-size: 12px;
}

.event-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  display: inline-block;
}

.event-dot-info {
  background: #12d7ff;
  box-shadow: 0 0 8px rgba(18, 215, 255, 0.52);
}

.event-dot-warn {
  background: #f6b73c;
  box-shadow: 0 0 8px rgba(246, 183, 60, 0.52);
}

.event-dot-error {
  background: #ff5d73;
  box-shadow: 0 0 8px rgba(255, 93, 115, 0.62);
  animation: blink 1.1s ease-in-out infinite;
}

.event-tag {
  text-align: center;
  border-radius: 999px;
  font-size: 11px;
  padding: 2px 0;
}

.event-info {
  color: #66d0ff;
  background: rgba(18, 215, 255, 0.14);
}

.event-warn {
  color: #f6b73c;
  background: rgba(246, 183, 60, 0.16);
}

.event-error {
  color: #ff6f83;
  background: rgba(255, 93, 115, 0.18);
}

.event-text {
  color: #d8ebff;
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

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
  padding: 24px 16px;
  font-size: 14px;
}

@media (max-width: 1280px) {
  .kpi-row {
    grid-template-columns: 1fr;
  }

  .dashboard-grid {
    grid-template-columns: 1fr;
  }

  .panel-trend,
  .panel-center {
    grid-column: 1;
  }

  .dashboard-bottom {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .weather-metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .event-item {
    grid-template-columns: 74px 48px 1fr;
  }
}
</style>
