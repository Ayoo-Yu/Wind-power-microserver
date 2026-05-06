<template>
  <div class="kpi-row">
    <div
      v-for="item in items"
      :key="item.key"
      class="kpi-card"
      :class="`kpi-${item.theme || 'cyan'}`"
    >
      <div class="kpi-deco"></div>
      <div class="kpi-label">{{ item.label }}</div>

      <div v-if="item.type === 'accuracy-split'" class="kpi-main">
        <span class="kpi-number">{{ ((item.value?.shortTerm || 0) + (item.value?.ultraShort || 0)) / 2 > 0
          ? ((item.value?.shortTerm || 0) + (item.value?.ultraShort || 0)) / 2
          : '--' }}</span>
        <span class="kpi-unit">%</span>
      </div>
      <div v-else class="kpi-main">
        <span class="kpi-number">{{ formatValue(item.value) }}</span>
        <span v-if="item.unit" class="kpi-unit">{{ item.unit }}</span>
      </div>

      <div v-if="item.type === 'accuracy-split'" class="kpi-sub-row">
        <span class="sub-label" style="color:#60a5fa">短期</span>
        <span class="sub-value" style="color:#60a5fa">{{ item.value?.shortTerm ?? '--' }}%</span>
        <span class="sub-sep"></span>
        <span class="sub-label" style="color:#fbbf24">超短期</span>
        <span class="sub-value" style="color:#fbbf24">{{ item.value?.ultraShort ?? '--' }}%</span>
      </div>
      <div v-else-if="item.sub?.length" class="kpi-sub-row">
        <template v-for="(s, i) in item.sub" :key="i">
          <span class="sub-label">{{ s.label }}</span>
          <span class="sub-value" :class="{ 'sub-highlight': s.highlight }">{{ s.value }}</span>
          <span v-if="i < item.sub.length - 1" class="sub-sep"></span>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  items: {
    type: Array,
    default: () => []
  }
})

function formatValue(val) {
  if (val == null) return '--'
  const n = Number(val)
  if (!Number.isFinite(n)) return '--'
  if (n >= 1000) return n.toLocaleString('en-US', { maximumFractionDigits: 0 })
  return n % 1 === 0 ? String(n) : n.toFixed(1)
}
</script>

<style scoped>
.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.kpi-card {
  position: relative;
  padding: 14px 16px;
  border-radius: 10px;
  overflow: hidden;
  min-height: 90px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.kpi-deco {
  position: absolute;
  top: 0;
  right: 0;
  width: 64px;
  height: 64px;
  pointer-events: none;
}

.kpi-label {
  font-size: 11px;
  color: #8fb2ca;
  margin-bottom: 4px;
}

.kpi-main {
  display: flex;
  align-items: baseline;
  gap: 3px;
}

.kpi-number {
  font-size: 26px;
  font-weight: 700;
  font-family: Consolas, Menlo, Monaco, monospace;
  line-height: 1.2;
}

.kpi-unit {
  font-size: 12px;
  margin-left: 1px;
}

.kpi-sub-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  flex-wrap: wrap;
}

.sub-label {
  font-size: 10px;
  color: #7a96aa;
}

.sub-value {
  font-size: 12px;
  font-weight: 600;
  color: #9fc4df;
}

.sub-highlight {
  color: #2dd36f;
}

.sub-sep {
  width: 1px;
  height: 12px;
  background: rgba(136, 186, 217, 0.15);
}

/* Theme variants */
.kpi-cyan {
  background: linear-gradient(135deg, rgba(18, 215, 255, 0.08), rgba(18, 215, 255, 0.02));
  border: 1px solid rgba(18, 215, 255, 0.18);
}
.kpi-cyan .kpi-number, .kpi-cyan .kpi-unit { color: #12d7ff; }
.kpi-cyan .kpi-deco { background: radial-gradient(circle at top right, rgba(18, 215, 255, 0.12), transparent); }

.kpi-green {
  background: linear-gradient(135deg, rgba(45, 211, 111, 0.08), rgba(45, 211, 111, 0.02));
  border: 1px solid rgba(45, 211, 111, 0.18);
}
.kpi-green .kpi-number, .kpi-green .kpi-unit { color: #2dd36f; }
.kpi-green .kpi-deco { background: radial-gradient(circle at top right, rgba(45, 211, 111, 0.12), transparent); }

.kpi-yellow {
  background: linear-gradient(135deg, rgba(251, 191, 36, 0.08), rgba(251, 191, 36, 0.02));
  border: 1px solid rgba(251, 191, 36, 0.18);
}
.kpi-yellow .kpi-number, .kpi-yellow .kpi-unit { color: #fbbf24; }
.kpi-yellow .kpi-deco { background: radial-gradient(circle at top right, rgba(251, 191, 36, 0.12), transparent); }

.kpi-purple {
  background: linear-gradient(135deg, rgba(167, 139, 250, 0.08), rgba(167, 139, 250, 0.02));
  border: 1px solid rgba(167, 139, 250, 0.18);
}
.kpi-purple .kpi-number, .kpi-purple .kpi-unit { color: #a78bfa; }
.kpi-purple .kpi-deco { background: radial-gradient(circle at top right, rgba(167, 139, 250, 0.12), transparent); }

@media (max-width: 720px) {
  .kpi-row {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
