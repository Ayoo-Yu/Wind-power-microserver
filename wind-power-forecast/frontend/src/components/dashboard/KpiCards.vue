<template>
  <div class="kpi-grid">
    <div v-for="item in items" :key="item.key" class="kpi-card panel-card">
      <div class="kpi-head">
        <span class="kpi-label">{{ item.label }}</span>
        <el-icon class="kpi-icon">
          <Aim />
        </el-icon>
      </div>

      <div v-if="item.type === 'accuracy-split'" class="kpi-body">
        <div class="accuracy-row">
          <div class="accuracy-item">
            <div class="accuracy-value">{{ item.value?.shortTerm ?? 0 }}<small>%</small></div>
            <div class="accuracy-label">短期</div>
          </div>
          <div class="accuracy-sep"></div>
          <div class="accuracy-item">
            <div class="accuracy-value">{{ item.value?.ultraShort ?? 0 }}<small>%</small></div>
            <div class="accuracy-label">超短期</div>
          </div>
        </div>
      </div>

      <div v-else class="kpi-body">
        <div class="value-big">{{ item.value }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Aim } from '@element-plus/icons-vue'

defineProps({
  items: {
    type: Array,
    default: () => []
  }
})
</script>

<style scoped>
.kpi-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
}

.kpi-card {
  padding: 10px 12px;
  position: relative;
  overflow: hidden;
}

.kpi-card::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  box-shadow: inset 0 0 14px rgba(18, 215, 255, 0.04);
}

.kpi-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.kpi-label {
  color: #8fb2ca;
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.kpi-icon {
  font-size: 15px;
  color: var(--accent);
  filter: drop-shadow(0 0 4px rgba(18, 215, 255, 0.2));
  flex-shrink: 0;
}

.kpi-body {
  margin-top: 6px;
}

.value-big {
  color: var(--text-primary);
  font-size: 20px;
  font-family: 'DIN Alternate', Consolas, Menlo, Monaco, monospace;
  font-weight: 700;
  letter-spacing: -0.5px;
  line-height: 1.2;
}

/* ---- accuracy split ---- */
.accuracy-row {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 6px;
  align-items: center;
}

.accuracy-sep {
  width: 1px;
  height: 26px;
  background: rgba(158, 192, 216, 0.18);
}

.accuracy-item {
  text-align: center;
}

.accuracy-value {
  color: var(--text-primary);
  font-size: 17px;
  font-weight: 600;
  font-family: 'DIN Alternate', Consolas, Menlo, Monaco, monospace;
}

.accuracy-value small {
  font-size: 10px;
  color: #8fb2ca;
  margin-left: 1px;
}

.accuracy-label {
  color: #7a96aa;
  font-size: 10px;
  margin-top: 1px;
}
</style>
