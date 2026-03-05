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
  const windSpeed = props.points.map(item => item.windSpeed)

  chart.setOption(
    {
      tooltip: { trigger: 'axis' },
      legend: {
        data: ['实际功率', '预测功率', '风速'],
        right: 0,
        textStyle: { color: '#d7ecff' }
      },
      grid: { top: 30, right: 18, bottom: 40, left: 58 },
      xAxis: {
        type: 'category',
        data: labels,
        axisLabel: { color: '#9fb6cc', hideOverlap: true },
        axisLine: { lineStyle: { color: 'rgba(159,182,204,.35)' } }
      },
      yAxis: [
        {
          type: 'value',
          name: '功率 (MW)',
          nameTextStyle: { color: '#8eb3cc' },
          axisLabel: { color: '#9fb6cc' },
          splitLine: { lineStyle: { color: 'rgba(159,182,204,.2)', type: 'dashed' } }
        },
        {
          type: 'value',
          name: '风速 (m/s)',
          nameTextStyle: { color: '#8eb3cc' },
          axisLabel: { color: '#9fb6cc' },
          splitLine: { show: false }
        }
      ],
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
          name: '实际功率',
          type: 'line',
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 2, color: '#2dd36f' },
          data: actual
        },
        {
          name: '预测功率',
          type: 'line',
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 2, color: '#12d7ff' },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(18,215,255,0.25)' },
              { offset: 1, color: 'rgba(18,215,255,0.02)' }
            ])
          },
          markPoint: {
            symbolSize: 26,
            label: { color: '#00111c', fontSize: 11 },
            data: [
              { type: 'max', name: '最大值', itemStyle: { color: '#53f0b0' } },
              { type: 'min', name: '最小值', itemStyle: { color: '#f6b73c' } }
            ]
          },
          data: predicted
        },
        {
          name: '风速',
          type: 'line',
          yAxisIndex: 1,
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 1.5, color: '#f6b73c', type: 'dashed' },
          data: windSpeed
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
