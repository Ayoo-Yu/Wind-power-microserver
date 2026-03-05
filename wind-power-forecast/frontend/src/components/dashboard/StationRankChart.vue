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

  const sortedRows = [...props.rows].sort((a, b) => b.value - a.value)
  const names = sortedRows.map(item => item.name)
  const values = sortedRows.map(item => item.value)

  chart.setOption(
    {
      grid: { top: 20, right: 40, bottom: 18, left: 112 },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: 'rgba(159,182,204,.2)', type: 'dashed' } },
        axisLabel: { color: '#9fb6cc' }
      },
      yAxis: {
        type: 'category',
        data: names,
        axisLabel: {
          color: '#d6ebff',
          formatter: (value, index) => {
            if (index === 0) return `{top|TOP1}  ${value}`
            return value
          },
          rich: {
            top: {
              color: '#f7c850',
              fontWeight: 700,
              fontSize: 11,
              padding: [1, 6, 1, 6],
              borderRadius: 10,
              backgroundColor: 'rgba(247, 200, 80, 0.14)'
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
              if (p.dataIndex === 0) {
                return new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                  { offset: 0, color: '#f7c850' },
                  { offset: 1, color: '#ff9f43' }
                ])
              }
              return new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                { offset: 0, color: '#1bb1ff' },
                { offset: 1, color: '#2dd36f' }
              ])
            }
          }
        }
      ]
    },
    true
  )
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
