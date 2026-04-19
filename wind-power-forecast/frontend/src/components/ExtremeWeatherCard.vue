<template>
  <div class="extreme-weather-card panel-card" :class="severityClass" @click="goToAlarm">
    <div class="ew-head">
      <span class="ew-label">极端天气</span>
      <el-icon class="ew-icon" :class="severityClass">
        <component :is="statusIcon" />
      </el-icon>
    </div>
    <div class="ew-body">
      <div class="ew-status-text" :class="severityClass">{{ statusLabel }}</div>
      <div v-if="statusMessage" class="ew-message">{{ statusMessage }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import farmService from '@/utils/farmService'
import { getWeatherStatus } from '@/api/extremeWeatherApi'

const SEVERITY_MAP = {
  normal: { icon: 'Sunny', label: '正常', cls: 'severity-normal' },
  info: { icon: 'WarningFilled', label: '注意', cls: 'severity-info' },
  warning: { icon: 'Warning', label: '预警', cls: 'severity-warning' },
  danger: { icon: 'CircleCloseFilled', label: '警报', cls: 'severity-danger' }
}

import { Sunny, WarningFilled, Warning, CircleCloseFilled } from '@element-plus/icons-vue'

const ICON_COMPONENTS = { Sunny, WarningFilled, Warning, CircleCloseFilled }

const router = useRouter()

const severity = ref('normal')
const statusMessage = ref('')

let farmListener = null

const severityClass = computed(() => {
  const entry = SEVERITY_MAP[severity.value]
  return entry ? entry.cls : 'severity-normal'
})

const statusIcon = computed(() => {
  const entry = SEVERITY_MAP[severity.value]
  const iconName = entry ? entry.icon : 'Sunny'
  return ICON_COMPONENTS[iconName] || Sunny
})

const statusLabel = computed(() => {
  const entry = SEVERITY_MAP[severity.value]
  return entry ? entry.label : '正常'
})

async function fetchStatus() {
  const farmCode = farmService.getCurrentFarm()
  try {
    const response = await getWeatherStatus(farmCode)
    const data = response?.data?.data || response?.data || {}
    severity.value = data.severity || 'normal'
    statusMessage.value = data.message || ''
  } catch {
    severity.value = 'normal'
    statusMessage.value = ''
  }
}

function goToAlarm() {
  router.push('/alarm')
}

onMounted(async () => {
  await fetchStatus()

  farmListener = async () => {
    await fetchStatus()
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
.extreme-weather-card {
  cursor: pointer;
  transition: border-color 0.3s, box-shadow 0.3s;
}

.extreme-weather-card:hover {
  box-shadow: 0 10px 22px rgba(7, 20, 33, 0.45), 0 0 18px rgba(18, 215, 255, 0.12);
}

.ew-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.ew-label {
  color: var(--text-secondary);
  font-size: 13px;
}

.ew-icon {
  font-size: 22px;
}

.ew-body {
  margin-top: 8px;
}

.ew-status-text {
  font-size: 18px;
  font-weight: 600;
  font-family: Consolas, Menlo, Monaco, monospace;
}

.ew-message {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Severity colors */
.severity-normal { color: #2dd36f; }
.severity-info { color: #f6b73c; }
.severity-warning { color: #ff9f43; }
.severity-danger { color: #ff5d73; animation: pulse-danger 1.4s ease-in-out infinite; }

.ew-icon.severity-normal { color: #2dd36f; filter: drop-shadow(0 0 6px rgba(45, 211, 111, 0.4)); }
.ew-icon.severity-info { color: #f6b73c; filter: drop-shadow(0 0 6px rgba(246, 183, 60, 0.4)); }
.ew-icon.severity-warning { color: #ff9f43; filter: drop-shadow(0 0 6px rgba(255, 159, 67, 0.4)); }
.ew-icon.severity-danger { color: #ff5d73; filter: drop-shadow(0 0 6px rgba(255, 93, 115, 0.5)); }

.extreme-weather-card.severity-normal { border-left: 3px solid #2dd36f; }
.extreme-weather-card.severity-info { border-left: 3px solid #f6b73c; }
.extreme-weather-card.severity-warning { border-left: 3px solid #ff9f43; }
.extreme-weather-card.severity-danger { border-left: 3px solid #ff5d73; }

@keyframes pulse-danger {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.65; }
}
</style>
