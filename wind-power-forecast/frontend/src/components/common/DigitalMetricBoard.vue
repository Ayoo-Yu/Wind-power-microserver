<template>
  <div class="digital-metric-board">
    <article
      v-for="metric in normalizedMetrics"
      :key="metric.id"
      class="digital-metric-card"
    >
      <div v-if="metric.label" class="digital-metric-card__label">
        {{ metric.label }}
      </div>
      <div class="digital-metric-card__value">
        {{ metric.value }}
        <span v-if="metric.unit" class="digital-metric-card__unit">{{ metric.unit }}</span>
      </div>
      <div v-if="metric.meta" class="digital-metric-card__meta">
        {{ metric.meta }}
      </div>
    </article>
  </div>
</template>

<script>
export default {
  name: 'DigitalMetricBoard',
  props: {
    metrics: {
      type: Array,
      default: () => [],
    },
  },
  computed: {
    normalizedMetrics() {
      return this.metrics.map((metric, index) => ({
        id: metric.id ?? metric.label ?? index,
        label: metric.label ?? '',
        value: metric.value ?? '',
        meta: metric.meta ?? metric.description ?? '',
        unit: metric.unit ?? '',
      }))
    },
  },
}
</script>
