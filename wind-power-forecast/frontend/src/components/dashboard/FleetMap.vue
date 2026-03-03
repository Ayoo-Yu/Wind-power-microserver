<template>
  <div ref="chartRef" class="chart-host" />
</template>

<script setup>
/* global defineProps */
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  points: {
    type: Array,
    default: () => []
  }
})

const chartRef = ref(null)
let chart

function render() {
  if (!chart) return
  chart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: (p) => `${p.data.name}<br/>场站编码: ${p.data.code || '-'}<br/>指数: ${p.data.value?.[2] || '-'}`
    },
    xAxis: { show: false, min: -60, max: 60 },
    yAxis: { show: false, min: -60, max: 60 },
    series: [
      {
        type: 'graph',
        layout: 'none',
        coordinateSystem: 'cartesian2d',
        symbol: 'circle',
        symbolSize: (v) => 10 + ((v?.[2] || 60) / 15),
        label: {
          show: true,
          color: '#d9ecff',
          fontSize: 11,
          formatter: '{b}'
        },
        itemStyle: {
          color: (p) => (p.data.status === 'warn' ? '#f6b73c' : '#12d7ff'),
          shadowBlur: 12,
          shadowColor: 'rgba(18, 215, 255, .45)'
        },
        data: props.points.map(item => ({
          ...item,
          value: item.value
        })),
        emphasis: { focus: 'adjacency' }
      }
    ]
  }, true)
}

onMounted(() => {
  chart = echarts.init(chartRef.value)
  render()
  window.addEventListener('resize', chart.resize)
})

watch(() => props.points, render, { deep: true })

onBeforeUnmount(() => {
  window.removeEventListener('resize', chart?.resize)
  chart?.dispose()
})
</script>

<style scoped>
.chart-host {
  height: 360px;
  width: 100%;
}
</style>
