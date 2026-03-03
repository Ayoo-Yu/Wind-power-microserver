<template>
  <div ref="chartRef" class="sparkline" />
</template>

<script setup>
/* global defineProps */
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  values: {
    type: Array,
    default: () => []
  }
})

const chartRef = ref(null)
let chart

function render() {
  if (!chart) return
  chart.setOption({
    xAxis: { type: 'category', show: false, data: props.values.map((_, i) => i) },
    yAxis: { type: 'value', show: false },
    grid: { left: 0, right: 0, top: 0, bottom: 0 },
    series: [{
      type: 'line',
      data: props.values,
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 1.5, color: '#12d7ff' },
      areaStyle: { color: 'rgba(18,215,255,.12)' }
    }]
  }, true)
}

onMounted(() => {
  chart = echarts.init(chartRef.value)
  render()
})

watch(() => props.values, render, { deep: true })

onBeforeUnmount(() => {
  chart?.dispose()
})
</script>

<style scoped>
.sparkline {
  width: 120px;
  height: 28px;
}
</style>
