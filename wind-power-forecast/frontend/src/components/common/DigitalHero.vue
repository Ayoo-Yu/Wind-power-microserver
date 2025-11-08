<template>
  <section class="digital-hero">
    <div class="digital-hero__content">
      <p v-if="eyebrow" class="digital-hero__eyebrow">{{ eyebrow }}</p>
      <h1 v-if="title" class="digital-hero__title">{{ title }}</h1>
      <p v-if="subtitle" class="digital-hero__subtitle">{{ subtitle }}</p>

      <div v-if="chipItems.length" class="digital-hero__chips">
        <span
          v-for="chip in chipItems"
          :key="chip.id"
          :class="['digital-chip', chip.variant ? `digital-chip--${chip.variant}` : '']"
        >
          {{ chip.label }}
        </span>
      </div>

      <div v-if="hasMeta" class="digital-hero__meta">
        <slot name="meta">
          <span v-if="tag" class="digital-status-chip">{{ tag }}</span>
        </slot>
      </div>

      <div v-if="$slots.actions" class="digital-hero__actions">
        <slot name="actions" />
      </div>
    </div>

    <div class="digital-hero__metrics">
      <slot name="metrics">
        <DigitalMetricBoard v-if="hasMetrics" :metrics="metrics" />
      </slot>
    </div>
  </section>
</template>

<script>
import DigitalMetricBoard from './DigitalMetricBoard.vue'

export default {
  name: 'DigitalHero',
  components: {
    DigitalMetricBoard,
  },
  props: {
    eyebrow: {
      type: String,
      default: '',
    },
    title: {
      type: String,
      default: '',
    },
    subtitle: {
      type: String,
      default: '',
    },
    chips: {
      type: Array,
      default: () => [],
    },
    tag: {
      type: String,
      default: '',
    },
    metrics: {
      type: Array,
      default: () => [],
    },
  },
  computed: {
    chipItems() {
      return this.chips.map((chip, index) => ({
        id: chip.id ?? chip.label ?? index,
        label: chip.label ?? chip,
        variant: chip.variant ?? '',
      }))
    },
    hasMeta() {
      return Boolean(this.tag || this.$slots.meta)
    },
    hasMetrics() {
      return Array.isArray(this.metrics) && this.metrics.length > 0
    },
  },
}
</script>
