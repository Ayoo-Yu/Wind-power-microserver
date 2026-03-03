<template>
  <div class="kpi-grid">
    <div v-for="item in items" :key="item.key" class="kpi-card panel-card">
      <div class="kpi-label">{{ item.label }}</div>
      <div class="kpi-value">{{ item.value }}<span class="kpi-unit">{{ item.unit }}</span></div>
    </div>
  </div>
</template>

<script setup>
/* global defineProps */
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
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.kpi-card {
  padding: 14px;
}

.kpi-label {
  color: var(--text-secondary);
  font-size: 13px;
}

.kpi-value {
  margin-top: 8px;
  font-size: 28px;
  font-family: "Consolas", "Courier New", monospace;
  font-weight: 700;
  color: var(--text-primary);
}

.kpi-unit {
  margin-left: 6px;
  font-size: 12px;
  color: var(--text-secondary);
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
