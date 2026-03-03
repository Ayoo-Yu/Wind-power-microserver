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
  const labels = props.points.map(item => item.time)
  const actual = props.points.map(item => item.actual)
  const predicted = props.points.map(item => item.predicted)

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: {
      data: ['实测', '预测'],
      right: 0,
      textStyle: { color: '#d7ecff' }
    },
    grid: { top: 30, right: 16, bottom: 40, left: 56 },
    xAxis: {
      type: 'category',
      data: labels,
      axisLabel: { color: '#9fb6cc', hideOverlap: true },
      axisLine: { lineStyle: { color: 'rgba(159,182,204,.35)' } }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#9fb6cc' },
      splitLine: { lineStyle: { color: 'rgba(159,182,204,.2)', type: 'dashed' } }
    },
    dataZoom: [
      { type: 'inside' },
      {
        type: 'slider',
        height: 16,
        bottom: 10,
        borderColor: 'rgba(159,182,204,.25)',
        backgroundColor: 'rgba(9,20,32,.6)',
        fillerColor: 'rgba(18,215,255,.2)'
      }
    ],
    series: [
      {
        name: '实测',
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: '#2dd36f' },
        data: actual
      },
      {
        name: '预测',
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: '#12d7ff' },
        areaStyle: { color: 'rgba(18,215,255,.08)' },
        data: predicted
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
  width: 100%;
  height: 320px;
}
</style>
