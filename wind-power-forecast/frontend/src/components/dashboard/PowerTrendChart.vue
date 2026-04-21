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
let chart = null
let disposed = false

function resolveNowIndex(labels) {
  const now = new Date()
  const nowMinutes = now.getHours() * 60 + now.getMinutes()
  let best = 0
  let bestDelta = Number.POSITIVE_INFINITY

  labels.forEach((label, idx) => {
    const m = String(label).match(/^(\d{2}):(\d{2})$/)
    if (!m) return
    const minutes = Number(m[1]) * 60 + Number(m[2])
    const delta = Math.abs(minutes - nowMinutes)
    if (delta < bestDelta) {
      bestDelta = delta
      best = idx
    }
  })
  return best
}

function render() {
  if (!chart || disposed) return
  if (!props.points?.length) return

  const labels = props.points.map(item => item.label || item.time)
  const actual = props.points.map(item => item.actual)
  const shortTerm = props.points.map(item => item.shortTerm)
  const ultraShort = props.points.map(item => item.ultraShort)
  const availableCap = props.points.map(item => item.availableCap)
  const nowIndex = resolveNowIndex(labels)

  chart.setOption(
    {
      tooltip: { trigger: 'axis' },
      legend: {
        data: ['实绩功率', '短期预测', '超短期预测', '可用容量上限'],
        right: 0,
        textStyle: { color: '#d7ecff' }
      },
      grid: { top: 30, right: 20, bottom: 42, left: 58 },
      xAxis: {
        type: 'category',
        data: labels,
        axisLabel: { color: '#9fb6cc', hideOverlap: true },
        axisLine: { lineStyle: { color: 'rgba(159,182,204,.35)' } },
        splitLine: { show: false }
      },
      yAxis: {
        type: 'value',
        name: '功率 (MW)',
        nameTextStyle: { color: '#8eb3cc' },
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
          name: '实绩功率',
          type: 'line',
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 2.2, color: '#2dd36f', type: 'solid' },
          data: actual
        },
        {
          name: '短期预测',
          type: 'line',
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 2, color: '#12d7ff', type: 'dashed' },
          data: shortTerm
        },
        {
          name: '超短期预测',
          type: 'line',
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 2, color: '#f6b73c', type: [8, 4, 2, 4] },
          data: ultraShort,
          markLine: {
            symbol: 'none',
            lineStyle: { color: '#ff5d73', width: 1.5, type: 'solid' },
            label: {
              show: true,
              formatter: '当前',
              color: '#ffb8c2',
              backgroundColor: 'rgba(255,93,115,.15)',
              padding: [2, 6, 2, 6]
            },
            data: [{ xAxis: nowIndex }]
          }
        },
        {
          name: '可用容量上限',
          type: 'line',
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 1.8, color: '#d7e4ef', type: 'solid' },
          data: availableCap
        }
      ]
    },
    true
  )
}

const handleResize = () => { if (!disposed && chart) chart.resize() }

onMounted(() => {
  chart = echarts.init(chartRef.value)
  render()
  window.addEventListener('resize', handleResize)
})

watch(() => props.points, render, { deep: true })

onBeforeUnmount(() => {
  disposed = true
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.chart-host {
  width: 100%;
  height: 360px;
}
</style>
