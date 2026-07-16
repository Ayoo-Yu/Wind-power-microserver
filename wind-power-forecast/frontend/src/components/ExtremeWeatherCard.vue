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
  unknown: { icon: 'QuestionFilled', label: '数据未接入', cls: 'severity-unknown' },
  normal: { icon: 'Sunny', label: '正常', cls: 'severity-normal' },
  info: { icon: 'WarningFilled', label: '注意', cls: 'severity-info' },
  warning: { icon: 'Warning', label: '预警', cls: 'severity-warning' },
  danger: { icon: 'CircleCloseFilled', label: '警报', cls: 'severity-danger' }
}

import { Sunny, WarningFilled, Warning, CircleCloseFilled, QuestionFilled } from '@element-plus/icons-vue'

const ICON_COMPONENTS = { Sunny, WarningFilled, Warning, CircleCloseFilled, QuestionFilled }

const router = useRouter()

const severity = ref('unknown')
const statusMessage = ref('正在检查实时天气数据源')

let farmListener = null

const severityClass = computed(() => {
  const entry = SEVERITY_MAP[severity.value]
  return entry ? entry.cls : 'severity-unknown'
})

const statusIcon = computed(() => {
  const entry = SEVERITY_MAP[severity.value]
  const iconName = entry ? entry.icon : 'QuestionFilled'
  return ICON_COMPONENTS[iconName] || QuestionFilled
})

const statusLabel = computed(() => {
  const entry = SEVERITY_MAP[severity.value]
  return entry ? entry.label : '数据未接入'
})

async function fetchStatus() {
  const farmCode = farmService.getCurrentFarm()
  try {
    const response = await getWeatherStatus(farmCode)
    const data = response?.data?.data || response?.data || {}
    const condition = data.current_condition || {}
    if (data.data_available === false || condition.type === 'unknown') {
      severity.value = 'unknown'
      statusMessage.value = data.message || '实时天气数据源尚未接入'
      return
    }
    severity.value = condition.severity || 'unknown'
    statusMessage.value = condition.type && condition.type !== 'normal' ? `${condition.type}` : ''
  } catch {
    severity.value = 'unknown'
    statusMessage.value = '天气状态接口不可用'
  }
}

function goToAlarm() {
  router.push('/alarm-center')
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
.severity-normal { color: var(--accent); }
.severity-unknown { color: var(--text-secondary); }
.severity-info { color: var(--accent-blue); }
.severity-warning { color: #966019; }
.severity-danger { color: #a64343; animation: pulse-danger 1.4s ease-in-out infinite; }

.ew-icon.severity-normal { color: var(--accent); }
.ew-icon.severity-unknown { color: var(--text-secondary); }
.ew-icon.severity-info { color: var(--accent-blue); }
.ew-icon.severity-warning { color: #966019; }
.ew-icon.severity-danger { color: #a64343; }

.extreme-weather-card.severity-normal { border-left: 3px solid var(--accent); }
.extreme-weather-card.severity-unknown { border-left: 3px solid var(--text-secondary); }
.extreme-weather-card.severity-info { border-left: 3px solid var(--accent-blue); }
.extreme-weather-card.severity-warning { border-left: 3px solid #966019; }
.extreme-weather-card.severity-danger { border-left: 3px solid #a64343; }

@keyframes pulse-danger {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.65; }
}
</style>
