<template>
  <div ref="chartRef" class="chart-host" />
</template>

<script setup>
/* global defineProps */
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  rows: {
    type: Array,
    default: () => []
  }
})

const chartRef = ref(null)
let chart

function render() {
  if (!chart) return
  const names = props.rows.map(item => item.name)
  const values = props.rows.map(item => item.value)

  chart.setOption({
    grid: { top: 20, right: 8, bottom: 18, left: 80 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(159,182,204,.2)', type: 'dashed' } },
      axisLabel: { color: '#9fb6cc' }
    },
    yAxis: {
      type: 'category',
      data: names,
      axisLabel: { color: '#d6ebff' }
    },
    series: [
      {
        type: 'bar',
        data: values,
        itemStyle: {
          borderRadius: [0, 6, 6, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: '#1bb1ff' },
            { offset: 1, color: '#2dd36f' }
          ])
        }
      }
    ]
  }, true)
}

onMounted(() => {
  chart = echarts.init(chartRef.value)
  render()
  window.addEventListener('resize', chart.resize)
})

watch(() => props.rows, render, { deep: true })

onBeforeUnmount(() => {
  window.removeEventListener('resize', chart?.resize)
  chart?.dispose()
})
</script>

<style scoped>
.chart-host {
  width: 100%;
  height: 320px;
}
</style>
