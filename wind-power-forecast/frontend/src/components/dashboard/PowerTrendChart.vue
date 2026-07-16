<template>
  <div class="chart-host">
    <div v-if="showRangeButtons" class="range-bar">
      <button
        v-for="opt in rangeOptions"
        :key="opt.value"
        class="range-btn"
        :class="{ active: currentRange === opt.value }"
        @click="selectRange(opt.value)"
      >{{ opt.label }}</button>
    </div>
    <div ref="chartRef" class="chart-canvas" />
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import * as echarts from '../../utils/echarts'

const props = defineProps({
  points: {
    type: Array,
    default: () => []
  },
  showRangeButtons: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['range-change'])

const rangeOptions = [
  { label: '1D', value: '1d' },
  { label: '3D', value: '3d' },
  { label: '7D', value: '7d' }
]

const currentRange = ref('1d')
const chartRef = ref(null)
let chart = null
let disposed = false

function selectRange(range) {
  currentRange.value = range
  emit('range-change', range)
}

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

  const tickInterval = Math.max(0, Math.floor(labels.length / 12))

  chart.setOption(
    {
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#ffffff',
        borderColor: '#dfe5e0',
        borderWidth: 1,
        textStyle: { color: '#17211b', fontSize: 12 },
        formatter: (params) => {
          if (!params?.length) return ''
          const time = params[0].axisValue
          let html = `<div style="font-size:12px;color:#667169;margin-bottom:4px">${time}</div>`
          params.forEach(p => {
            const val = p.value != null ? Number(p.value).toFixed(1) + ' MW' : '--'
            html += `<div style="display:flex;justify-content:space-between;gap:16px;font-size:12px"><span>${p.marker} ${p.seriesName}</span><span style="font-weight:600;color:#17211b">${val}</span></div>`
          })
          return html
        }
      },
      legend: {
        data: [
          { name: '实绩功率', icon: 'path://M0,4L12,4', itemStyle: { color: '#247a52' } },
          { name: '短期预测', icon: 'path://M0,4L4,4L6,1L8,7L10,4L12,4', itemStyle: { color: '#397b91' } },
          { name: '超短期预测', icon: 'path://M0,4L3,4L4,1L5,7L6,4L9,4L10,1L11,7L12,4', itemStyle: { color: '#b7791f' } },
          { name: '可用容量上限', icon: 'path://M0,4L12,4', itemStyle: { color: '#7c6f9b' } }
        ],
        top: 0,
        left: 'center',
        itemWidth: 16,
        itemHeight: 8,
        textStyle: { color: '#667169', fontSize: 11 }
      },
      grid: { top: 34, right: 28, bottom: 38, left: 52 },
      xAxis: {
        type: 'category',
        data: labels,
        axisLabel: {
          color: '#768078',
          fontSize: 11,
          interval: tickInterval,
          formatter: (val) => {
            const m = String(val).match(/^(\d{2}):00$/)
            return m ? val : ''
          }
        },
        axisLine: { lineStyle: { color: '#dfe5e0' } },
        splitLine: { show: false }
      },
      yAxis: {
        type: 'value',
        name: 'MW',
        nameTextStyle: { color: '#768078', fontSize: 11 },
        axisLabel: { color: '#768078', fontSize: 11 },
        splitLine: { lineStyle: { color: '#e8ece9', type: 'dashed' } }
      },
      dataZoom: [
        { type: 'inside' },
        {
          type: 'slider',
          height: 14,
          bottom: 6,
          borderColor: '#dfe5e0',
          backgroundColor: '#f7f9f7',
          fillerColor: 'rgba(36,122,82,.16)'
        }
      ],
      series: [
        {
          name: '实绩功率',
          type: 'line',
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 2.2, color: '#247a52', type: 'solid' },
          data: actual
        },
        {
          name: '短期预测',
          type: 'line',
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 2, color: '#397b91', type: 'dashed' },
          data: shortTerm
        },
        {
          name: '超短期预测',
          type: 'line',
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 2, color: '#b7791f', type: [8, 4, 2, 4] },
          data: ultraShort,
          markLine: {
            symbol: 'none',
            lineStyle: { color: '#aeb7b0', width: 1.5, type: 'dashed' },
            label: {
              show: true,
              position: 'start',
              rotate: 0,
              formatter: () => {
                const d = new Date()
                const hh = String(d.getHours()).padStart(2, '0')
                const mm = String(d.getMinutes()).padStart(2, '0')
                return `当前 ${hh}:${mm}`
              },
              color: '#3e4941',
              fontSize: 11,
              backgroundColor: '#f2f5f2',
              padding: [3, 8, 3, 8],
              borderRadius: 3
            },
            data: [{ xAxis: nowIndex }]
          }
        },
        {
          name: '可用容量上限',
          type: 'line',
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 1.5, color: '#7c6f9b', type: 'solid' },
          areaStyle: { color: 'rgba(124,111,155,0.08)' },
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
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.range-bar {
  display: flex;
  gap: 4px;
  margin-bottom: 6px;
  flex-shrink: 0;
}

.range-btn {
  padding: 2px 10px;
  font-size: 11px;
  color: var(--text-muted);
  background: var(--surface);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.range-btn:hover {
  color: var(--primary);
  border-color: var(--primary);
}

.range-btn.active {
  color: var(--primary);
  background: var(--primary-soft);
  border-color: rgba(36, 122, 82, 0.32);
}

.chart-canvas {
  flex: 1;
  min-height: 180px;
}
</style>
