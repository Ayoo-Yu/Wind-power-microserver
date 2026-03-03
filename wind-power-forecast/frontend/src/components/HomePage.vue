<template>
  <div class="page-shell home-dashboard">
    <div class="dashboard-head panel-card">
      <div>
        <h1>风电功率预测数字驾驶舱</h1>
        <p>更新于：{{ updatedAt }}</p>
      </div>
      <el-button type="primary" :loading="loading" @click="loadData">刷新数据</el-button>
    </div>

    <KpiCards :items="cards" />

    <div class="dashboard-grid">
      <div class="panel-card panel-left">
        <div class="panel-title">各场站出力排行</div>
        <StationRankChart :rows="rankRows" />
      </div>

      <div class="panel-card panel-center">
        <div class="panel-title">场站拓扑分布</div>
        <FleetMap :points="topologyPoints" />
      </div>

      <div class="panel-card panel-right">
        <div class="panel-title">全天功率预测曲线</div>
        <PowerTrendChart :points="trendPoints" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import farmService from '@/utils/farmService'
import { getDashboardOverview, getDashboardStationRank, getDashboardTrend } from '@/services/dashboardService'
import KpiCards from '@/components/dashboard/KpiCards.vue'
import FleetMap from '@/components/dashboard/FleetMap.vue'
import StationRankChart from '@/components/dashboard/StationRankChart.vue'
import PowerTrendChart from '@/components/dashboard/PowerTrendChart.vue'

const loading = ref(false)
const cards = ref([])
const topologyPoints = ref([])
const rankRows = ref([])
const trendPoints = ref([])
const updatedAt = ref('--')

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
    const [overview, rank, trend] = await Promise.all([
      getDashboardOverview({ farmCode }),
      getDashboardStationRank({ farmCode }),
      getDashboardTrend({ farmCode })
    ])

    cards.value = overview.cards || []
    topologyPoints.value = overview.topology || []
    rankRows.value = rank || []
    trendPoints.value = trend || []
    updatedAt.value = formatNow()
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await farmService.loadAvailableFarms()
  loadData()
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
}

.dashboard-head p {
  margin: 6px 0 0;
  font-size: 13px;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: 1fr 1.2fr 1fr;
  gap: 12px;
}

.panel-card {
  padding: 12px;
}

.panel-title {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 10px;
}

@media (max-width: 1180px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
}
</style>
