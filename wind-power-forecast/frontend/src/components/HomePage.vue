<template>
  <div class="page-shell home-dashboard">
    <div class="dashboard-head panel-card">
      <div class="title-wrap">
        <h1>风电数字驾驶舱</h1>
        <p>更新时间：{{ updatedAt }}</p>
        <div class="title-deco">
          <span class="title-dot"></span>
          <i class="title-line"></i>
        </div>
      </div>
      <el-button type="primary" :loading="loading" @click="loadData">刷新</el-button>
    </div>

    <KpiCards :items="cards" />

    <div class="dashboard-grid">
      <div class="panel-card panel-left">
        <div class="panel-title">场站出力排名</div>
        <StationRankChart :rows="rankRows" />
      </div>

      <div class="panel-card panel-center">
        <div class="panel-title">场站拓扑</div>
        <FleetMap :points="topologyPoints" />
      </div>

      <div class="panel-card panel-right">
        <div class="panel-title">日功率预测</div>
        <PowerTrendChart :points="trendPoints" />
      </div>
    </div>

    <div class="dashboard-bottom">
      <div class="panel-card weather-card">
        <div class="panel-title">气象概览</div>
        <div class="weather-grid">
          <div v-for="item in weatherRows" :key="item.code" class="weather-item">
            <div class="weather-name">{{ item.name }}</div>
            <div class="weather-main">
              <div class="weather-wind-wrap">
                <i class="wind-icon"></i>
                <span class="weather-wind">{{ item.windSpeed }} m/s</span>
              </div>
              <span class="weather-dir">{{ item.windDirection }}</span>
            </div>
            <div class="wind-level">
              <span class="wind-level-fill" :style="windLevelStyle(item.windSpeed)"></span>
            </div>
            <div class="weather-sub">温度 {{ item.temperature }} C - 气压 {{ item.pressure }} hPa</div>
          </div>
        </div>
      </div>

      <div class="panel-card events-card">
        <div class="panel-title">实时事件 / 告警</div>
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
import FleetMap from '@/components/dashboard/FleetMap.vue'
import StationRankChart from '@/components/dashboard/StationRankChart.vue'
import PowerTrendChart from '@/components/dashboard/PowerTrendChart.vue'

const loading = ref(false)
const cards = ref([])
const topologyPoints = ref([])
const rankRows = ref([])
const trendPoints = ref([])
const weatherRows = ref([])
const events = ref([])
const updatedAt = ref('--')
let eventTicker = null

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
    weatherRows.value = weather || []
    events.value = eventRows || []
    updatedAt.value = formatNow()
  } finally {
    loading.value = false
  }
}

function windLevelStyle(speed) {
  const numeric = Number(speed) || 0
  const ratio = Math.max(0, Math.min(1, numeric / 15))
  const width = `${Math.round(ratio * 100)}%`
  let background = '#2dd36f'
  if (numeric >= 10) background = '#ff7d45'
  else if (numeric >= 7) background = '#f6b73c'
  return { width, background }
}

const scrollingEvents = computed(() => events.value.slice(0, 8))

function startEventTicker() {
  if (eventTicker) clearInterval(eventTicker)
  eventTicker = setInterval(() => {
    if (events.value.length > 1) {
      const first = events.value.shift()
      events.value.push(first)
    }
  }, 2600)
}

onMounted(async () => {
  await farmService.loadAvailableFarms()
  await loadData()
  startEventTicker()
})

onBeforeUnmount(() => {
  if (eventTicker) {
    clearInterval(eventTicker)
    eventTicker = null
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

.dashboard-grid {
  display: grid;
  grid-template-columns: 1fr 1.25fr 1fr;
  gap: 12px;
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

.weather-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.weather-item {
  border: 1px solid rgba(136, 186, 217, 0.2);
  border-radius: 10px;
  background: rgba(7, 24, 39, 0.58);
  padding: 10px;
}

.weather-name {
  font-size: 13px;
  color: #dbefff;
}

.weather-main {
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.weather-wind-wrap {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.wind-icon {
  width: 14px;
  height: 14px;
  border: 2px solid #77dcff;
  border-left-color: transparent;
  border-radius: 50%;
  display: inline-block;
  animation: spin 1.2s linear infinite;
}

.weather-wind {
  font-family: Consolas, Menlo, Monaco, monospace;
  color: #53f0b0;
  font-size: 20px;
  text-shadow: 0 0 10px rgba(83, 240, 176, 0.28);
}

.weather-dir {
  color: #9fd5f7;
  font-size: 13px;
}

.wind-level {
  margin-top: 8px;
  width: 100%;
  height: 5px;
  border-radius: 999px;
  background: rgba(110, 157, 190, 0.26);
  overflow: hidden;
}

.wind-level-fill {
  display: block;
  height: 100%;
  border-radius: 999px;
  transition: width 0.35s ease;
}

.weather-sub {
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.event-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 190px;
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

@media (max-width: 1280px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }

  .dashboard-bottom {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .weather-grid {
    grid-template-columns: 1fr;
  }

  .event-item {
    grid-template-columns: 74px 48px 1fr;
  }
}
</style>
