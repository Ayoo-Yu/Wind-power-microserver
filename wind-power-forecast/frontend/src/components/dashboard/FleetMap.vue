<template>
  <div class="map-shell">
    <div ref="chartRef" class="chart-host" />
    <span class="center-ripple ripple-a"></span>
    <span class="center-ripple ripple-b"></span>
  </div>
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

  const sourceNodes = props.points.map(item => ({
    name: item.name,
    code: item.code,
    status: item.status,
    value: item.value,
    virtual: false
  }))
  const decorativeNodes = Array.from({ length: 7 }).map((_, idx) => {
    const angle = (Math.PI * 2 * idx) / 7
    const radius = 52 + (idx % 2) * 10
    return {
      name: `N-${idx + 1}`,
      code: `VIRTUAL-${idx + 1}`,
      status: 'ok',
      value: [Math.round(Math.cos(angle) * radius), Math.round(Math.sin(angle) * radius), 40 + idx * 4],
      virtual: true
    }
  })
  const nodes = [...sourceNodes, ...decorativeNodes]

  const linesData = nodes.map(item => ({ coords: [[0, 0], [item.value?.[0] || 0, item.value?.[1] || 0]] }))

  chart.setOption(
    {
      grid: { top: 8, right: 6, bottom: 10, left: 6 },
      tooltip: {
        trigger: 'item',
        formatter: (p) => {
          if (!p?.data) return ''
          const health = p.data.value?.[2] || '-'
          return `${p.data.name}<br/>编码：${p.data.code || '-'}<br/>健康指数：${health}`
        }
      },
      xAxis: { type: 'value', min: -70, max: 70, show: false },
      yAxis: { type: 'value', min: -70, max: 70, show: false },
      graphic: [
        {
          type: 'circle',
          left: 'center',
          top: 'middle',
          shape: { r: 120 },
          style: { stroke: 'rgba(18, 215, 255, 0.18)', lineWidth: 1, fill: 'transparent' },
          silent: true
        },
        {
          type: 'circle',
          left: 'center',
          top: 'middle',
          shape: { r: 76 },
          style: { stroke: 'rgba(18, 215, 255, 0.14)', lineWidth: 1, fill: 'transparent' },
          silent: true
        }
      ],
      series: [
        {
          type: 'lines',
          coordinateSystem: 'cartesian2d',
          z: 1,
          effect: { show: true, period: 4, trailLength: 0.15, symbolSize: 4, color: 'rgba(18, 215, 255, 0.85)' },
          lineStyle: { width: 1, color: 'rgba(18, 215, 255, 0.22)', curveness: 0.18 },
          data: linesData
        },
        {
          type: 'scatter',
          coordinateSystem: 'cartesian2d',
          z: 2,
          symbolSize: 10,
          itemStyle: { color: '#1fe3ff', shadowBlur: 14, shadowColor: 'rgba(18, 215, 255, 0.42)' },
          data: [{ value: [0, 0], name: '控制中心', code: 'CONTROL' }],
          label: { show: true, position: 'bottom', color: '#dff1ff', fontSize: 11, formatter: '{b}' }
        },
        {
          type: 'effectScatter',
          coordinateSystem: 'cartesian2d',
          z: 4,
          rippleEffect: { period: 4, scale: 5, brushType: 'stroke' },
          symbolSize: 16,
          itemStyle: {
            color: '#12d7ff',
            shadowBlur: 20,
            shadowColor: 'rgba(18, 215, 255, 0.65)'
          },
          data: [{ value: [0, 0], name: '信号核心', code: 'CORE', virtual: true }],
          label: { show: false }
        },
        {
          type: 'effectScatter',
          coordinateSystem: 'cartesian2d',
          z: 3,
          rippleEffect: { period: 4, scale: 3, brushType: 'stroke' },
          symbolSize: (v) => 10 + ((v?.[2] || 60) / 16),
          itemStyle: {
            color: (p) => (p.data.status === 'warn' ? '#f6b73c' : '#2dd36f'),
            shadowBlur: 16,
            shadowColor: 'rgba(18, 215, 255, 0.45)'
          },
          label: {
            show: true,
            color: '#d9ecff',
            fontSize: 11,
            formatter: (p) => (p.data.virtual ? '' : p.data.name),
            position: 'top'
          },
          data: nodes
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
.map-shell {
  position: relative;
}

.chart-host {
  height: 360px;
  width: 100%;
}

.center-ripple {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  border: 1px solid rgba(18, 215, 255, 0.5);
  transform: translate(-50%, -50%);
  pointer-events: none;
  animation: ripple 3.6s linear infinite;
}

.ripple-b {
  animation-delay: 1.8s;
}

@keyframes ripple {
  0% {
    width: 8px;
    height: 8px;
    opacity: 0.75;
  }
  100% {
    width: 150px;
    height: 150px;
    opacity: 0;
  }
}
</style>
