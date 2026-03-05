<template>
  <div class="kpi-grid">
    <div v-for="item in items" :key="item.key" class="kpi-card panel-card">
      <div class="kpi-head">
        <span class="kpi-label">{{ item.label }}</span>
        <el-icon class="kpi-icon" :class="`kpi-icon-${item.key}`">
          <component :is="resolveIcon(item.key)" />
        </el-icon>
      </div>
      <div class="kpi-value">{{ displayValue(item) }}<span class="kpi-unit">{{ item.unit }}</span></div>
      <div class="kpi-trend" :class="item.trend === 'up' ? 'trend-up' : 'trend-down'">
        <span>{{ item.trend === 'up' ? '上升' : '下降' }} {{ item.delta }}</span>
        <small>较昨日</small>
      </div>
    </div>
  </div>
</template>

<script setup>
/* global defineProps */
import { onBeforeUnmount, ref, watch } from 'vue'
import { OfficeBuilding, Aim, Lightning, Bell } from '@element-plus/icons-vue'

const props = defineProps({
  items: {
    type: Array,
    default: () => []
  }
})
const displayMap = ref({})
let frameId = 0

function parseNumeric(value) {
  if (value === null || value === undefined) return null
  const normalized = String(value).replace(/,/g, '')
  const n = Number(normalized)
  return Number.isFinite(n) ? n : null
}

function displayValue(item) {
  const animated = displayMap.value[item.key]
  if (animated !== undefined) return animated
  return item.value
}

function formatAnimatedValue(target, current) {
  const isDecimal = String(target).includes('.')
  if (isDecimal) {
    return current.toFixed(1)
  }
  return Math.round(current).toLocaleString('en-US')
}

function animateValues() {
  if (frameId) cancelAnimationFrame(frameId)
  const startAt = performance.now()
  const duration = 900
  const trackers = props.items.map((item) => {
    const target = parseNumeric(item.value)
    if (target === null) {
      displayMap.value[item.key] = item.value
      return null
    }
    return { key: item.key, target }
  }).filter(Boolean)

  const tick = (now) => {
    const progress = Math.min((now - startAt) / duration, 1)
    const eased = 1 - Math.pow(1 - progress, 3)
    trackers.forEach(({ key, target }) => {
      displayMap.value[key] = formatAnimatedValue(target, target * eased)
    })
    if (progress < 1) {
      frameId = requestAnimationFrame(tick)
    }
  }

  frameId = requestAnimationFrame(tick)
}

watch(() => props.items, animateValues, { deep: true, immediate: true })

onBeforeUnmount(() => {
  if (frameId) cancelAnimationFrame(frameId)
})

function resolveIcon(key) {
  if (key === 'farm_total') return OfficeBuilding
  if (key === 'accuracy') return Aim
  if (key === 'power') return Lightning
  if (key === 'alerts') return Bell
  return OfficeBuilding
}
</script>

<style scoped>
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.kpi-card {
  padding: 14px;
}

.kpi-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.kpi-label {
  color: var(--text-secondary);
  font-size: 13px;
}

.kpi-icon {
  font-size: 18px;
  color: #63ddff;
  filter: drop-shadow(0 0 8px rgba(18, 215, 255, 0.42));
}

.kpi-icon-alerts {
  color: #ff7b92;
  filter: drop-shadow(0 0 8px rgba(255, 93, 115, 0.32));
}

.kpi-value {
  margin-top: 8px;
  font-size: 30px;
  font-family: Consolas, Menlo, Monaco, monospace;
  font-weight: 700;
  color: #49ecff;
  text-shadow: 0 0 11px rgba(18, 215, 255, 0.24);
}

.kpi-unit {
  margin-left: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  text-shadow: none;
}

.kpi-trend {
  margin-top: 6px;
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 12px;
}

.kpi-trend small {
  color: #89a6bd;
}

.trend-up {
  color: #2dd36f;
}

.trend-down {
  color: #ff5d73;
}

@media (max-width: 1100px) {
  .kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .kpi-grid {
    grid-template-columns: 1fr;
  }
}
</style>
