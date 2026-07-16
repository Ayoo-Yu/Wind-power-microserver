<template>
  <div ref="chartRef" class="chart-host" />
</template>

<script setup>
/* global defineProps */
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import * as echarts from '../../utils/echarts'

const props = defineProps({
  rows: {
    type: Array,
    default: () => []
  }
})

const chartRef = ref(null)
let chart = null
let disposed = false

function render() {
  if (!chart || disposed) return
  if (!props.rows?.length) return

  const sortedRows = [...props.rows].sort((a, b) => b.value - a.value)
  const names = sortedRows.map(item => item.name)
  const values = sortedRows.map(item => item.value)
  const barHeight = 20
  const barGap = 8
  const chartHeight = Math.min(Math.max(160, names.length * (barHeight + barGap) + 30), 360)
  chartRef.value.style.height = `${chartHeight}px`
  chart.resize()

  chart.setOption(
    {
      grid: { top: 16, right: 36, bottom: 14, left: 100 },
      tooltip: {
        trigger: 'axis',
        formatter: (params) => {
          if (!params?.length) return ''
          const p = params[0]
          return `${p.marker} ${p.name}<br/><span style="font-weight:600">${Number(p.value).toFixed(1)} MW</span>`
        }
      },
      xAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: 'rgba(159,182,204,.12)', type: 'dashed' } },
        axisLabel: { color: '#8ba4b8', fontSize: 11 }
      },
      yAxis: {
        type: 'category',
        data: names,
        axisLabel: {
          color: '#d6ebff',
          formatter: (value, index) => {
            if (index === 0) return `{top|TOP} ${value}`
            return value
          },
          rich: {
            top: {
              color: '#f7c850',
              fontWeight: 700,
              fontSize: 9,
              padding: [0, 3, 0, 3],
              borderRadius: 3,
              backgroundColor: 'rgba(247, 200, 80, 0.12)'
            }
          }
        }
      },
      series: [
        {
          type: 'bar',
          barWidth: 14,
          data: values,
          label: {
            show: true,
            position: 'right',
            color: '#d9f2ff',
            formatter: (p) => `${Number(p.value).toFixed(1)}`
          },
          itemStyle: {
            borderRadius: [0, 6, 6, 0],
            color: (p) => {
              const ratio = names.length > 1 ? p.dataIndex / (names.length - 1) : 0
              return new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                { offset: 0, color: '#0ea5e9' },
                { offset: 1, color: `rgba(14, 165, 233, ${0.55 + ratio * 0.45})` }
              ])
            }
          }
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

watch(() => props.rows, render, { deep: true })

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
  flex: 1;
  min-height: 160px;
  max-height: 360px;
}
</style>
