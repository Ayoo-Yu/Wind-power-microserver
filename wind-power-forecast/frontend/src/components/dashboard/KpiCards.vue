<template>
  <div class="kpi-row">
    <div
      v-for="item in items"
      :key="item.key"
      class="kpi-card"
      :class="`kpi-${item.theme || 'cyan'}`"
    >
      <div class="kpi-label">{{ item.label }}</div>

      <div v-if="item.type === 'accuracy-split'" class="kpi-main">
        <span class="kpi-number">{{ formatAccuracy(item.value) }}</span>
        <span class="kpi-unit">%</span>
      </div>
      <div v-else class="kpi-main">
        <span class="kpi-number">{{ formatValue(item.value) }}</span>
        <span v-if="item.unit" class="kpi-unit">{{ item.unit }}</span>
      </div>

      <div v-if="item.type === 'accuracy-split'" class="kpi-sub-row">
        <span class="sub-label sub-short">短期</span>
        <span class="sub-value sub-short">{{ item.value?.shortTerm ?? '--' }}%</span>
        <span class="sub-sep"></span>
        <span class="sub-label sub-ultra">超短期</span>
        <span class="sub-value sub-ultra">{{ item.value?.ultraShort ?? '--' }}%</span>
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

function formatAccuracy(value) {
  const s = Number(value?.shortTerm) || 0
  const u = Number(value?.ultraShort) || 0
  const avg = (s + u) / 2
  return avg > 0 ? avg.toFixed(2) : '--'
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
  padding: 16px 18px;
  border: 1px solid var(--border-light);
  border-radius: 14px;
  background: var(--surface);
  overflow: hidden;
  min-height: 108px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  box-shadow: var(--shadow-card);
}

.kpi-label {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.kpi-main {
  display: flex;
  align-items: baseline;
  gap: 3px;
}

.kpi-number {
  font-size: 28px;
  font-weight: 650;
  font-family: var(--font-mono);
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
  border-top: 1px solid var(--border-light);
  flex-wrap: wrap;
}

.sub-label {
  font-size: 10px;
  color: var(--text-muted);
}

.sub-value {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.sub-highlight {
  color: var(--success);
}

.sub-sep {
  width: 1px;
  height: 12px;
  background: var(--border-color);
}

.sub-short { color: #397b91; }
.sub-ultra { color: #b7791f; }
.kpi-cyan .kpi-number, .kpi-cyan .kpi-unit { color: #397b91; }
.kpi-green .kpi-number, .kpi-green .kpi-unit { color: #247a52; }
.kpi-yellow .kpi-number, .kpi-yellow .kpi-unit { color: #b7791f; }
.kpi-purple .kpi-number, .kpi-purple .kpi-unit { color: #7c6f9b; }

@media (max-width: 720px) {
  .kpi-row {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
