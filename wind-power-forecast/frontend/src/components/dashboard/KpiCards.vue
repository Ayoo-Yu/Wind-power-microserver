<template>
  <div class="kpi-grid">
    <div v-for="item in items" :key="item.key" class="kpi-card panel-card">
      <div class="kpi-head">
        <span class="kpi-label">{{ item.label }}</span>
        <el-icon class="kpi-icon">
          <component :is="resolveIcon(item.key)" />
        </el-icon>
      </div>

      <div v-if="item.type === 'station-comm'" class="kpi-body">
        <div class="kpi-main">
          正常运行:
          <strong>{{ item.value?.online ?? 0 }}</strong>
          / 总场站:
          <strong>{{ item.value?.total ?? 0 }}</strong>
        </div>
        <div class="kpi-subline">
          离线:
          <span class="danger">{{ item.value?.offline ?? 0 }}</span>
        </div>
      </div>

      <div v-else-if="item.type === 'power-capacity'" class="kpi-body kpi-body-row">
        <div class="kpi-main">
          <strong>{{ item.value?.power ?? 0 }}</strong> / <strong>{{ item.value?.capacity ?? 0 }}</strong> MW
        </div>
        <div class="load-ring" :style="ringStyle(item.value?.loadRate)">
          <span>{{ Math.round(item.value?.loadRate || 0) }}%</span>
        </div>
      </div>

      <div v-else-if="item.type === 'accuracy-split'" class="kpi-body">
        <div class="kpi-main">综合准确率</div>
        <div class="kpi-subline">
          短期准确率 {{ item.value?.shortTerm ?? 0 }}%
          <span class="sep">|</span>
          超短期准确率 {{ item.value?.ultraShort ?? 0 }}%
        </div>
      </div>

      <div v-else-if="item.type === 'report-completion'" class="kpi-body">
        <div class="kpi-main">超短期成功: {{ item.value?.ultraSuccess ?? 0 }}/{{ item.value?.ultraExpected ?? 0 }}</div>
        <div class="kpi-subline">短期成功: {{ item.value?.shortSuccess ?? 0 }}/{{ item.value?.shortExpected ?? 0 }}</div>
      </div>

      <div v-else class="kpi-body">
        <div class="kpi-main">{{ item.value }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
/* global defineProps */
import { OfficeBuilding, Aim, Lightning, Bell } from '@element-plus/icons-vue'

defineProps({
  items: {
    type: Array,
    default: () => []
  }
})

function resolveIcon(key) {
  if (key === 'station_comm') return OfficeBuilding
  if (key === 'accuracy') return Aim
  if (key === 'power_capacity') return Lightning
  if (key === 'report_completion') return Bell
  return OfficeBuilding
}

function ringStyle(rate) {
  const value = Math.max(0, Math.min(100, Number(rate) || 0))
  return {
    background: `conic-gradient(#12d7ff ${value * 3.6}deg, rgba(125, 170, 200, 0.2) 0deg)`
  }
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
}

.kpi-body {
  margin-top: 10px;
}

.kpi-body-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.kpi-main {
  color: #dff3ff;
  font-size: 20px;
  font-family: Consolas, Menlo, Monaco, monospace;
}

.kpi-main strong {
  color: #49ecff;
}

.kpi-subline {
  margin-top: 8px;
  font-size: 13px;
  color: #9ec0d8;
}

.danger {
  color: #ff5d73;
  font-weight: 700;
}

.sep {
  margin: 0 8px;
  color: rgba(158, 192, 216, 0.5);
}

.load-ring {
  width: 54px;
  height: 54px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  flex: 0 0 auto;
}

.load-ring::after {
  content: '';
  position: absolute;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: rgba(6, 24, 39, 0.94);
}

.load-ring span {
  position: relative;
  z-index: 1;
  color: #dff3ff;
  font-size: 12px;
  font-family: Consolas, Menlo, Monaco, monospace;
}

@media (max-width: 1280px) {
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
