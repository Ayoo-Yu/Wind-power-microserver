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
        backgroundColor: 'rgba(10, 22, 40, 0.92)',
        borderColor: 'rgba(18, 215, 255, 0.2)',
        borderWidth: 1,
        textStyle: { color: '#dff3ff', fontSize: 12 },
        formatter: (params) => {
          if (!params?.length) return ''
          const time = params[0].axisValue
          let html = `<div style="font-size:12px;color:#9fc4df;margin-bottom:4px">${time}</div>`
          params.forEach(p => {
            const val = p.value != null ? Number(p.value).toFixed(1) + ' MW' : '--'
            html += `<div style="display:flex;justify-content:space-between;gap:16px;font-size:12px"><span>${p.marker} ${p.seriesName}</span><span style="font-weight:600;color:#dff3ff">${val}</span></div>`
          })
          return html
        }
      },
      legend: {
        data: [
          { name: '实绩功率', icon: 'path://M0,4L12,4', itemStyle: { color: '#2dd4bf' } },
          { name: '短期预测', icon: 'path://M0,4L4,4L6,1L8,7L10,4L12,4', itemStyle: { color: '#60a5fa' } },
          { name: '超短期预测', icon: 'path://M0,4L3,4L4,1L5,7L6,4L9,4L10,1L11,7L12,4', itemStyle: { color: '#fbbf24' } },
          { name: '可用容量上限', icon: 'path://M0,4L12,4', itemStyle: { color: '#a78bfa' } }
        ],
        top: 0,
        left: 'center',
        itemWidth: 16,
        itemHeight: 8,
        textStyle: { color: '#9fc4df', fontSize: 11 }
      },
      grid: { top: 34, right: 28, bottom: 38, left: 52 },
      xAxis: {
        type: 'category',
        data: labels,
        axisLabel: {
          color: '#7a96aa',
          fontSize: 11,
          interval: tickInterval,
          formatter: (val) => {
            const m = String(val).match(/^(\d{2}):00$/)
            return m ? val : ''
          }
        },
        axisLine: { lineStyle: { color: 'rgba(159,182,204,.18)' } },
        splitLine: { show: false }
      },
      yAxis: {
        type: 'value',
        name: 'MW',
        nameTextStyle: { color: '#7a96aa', fontSize: 11 },
        axisLabel: { color: '#7a96aa', fontSize: 11 },
        splitLine: { lineStyle: { color: 'rgba(159,182,204,.08)', type: 'dashed' } }
      },
      dataZoom: [
        { type: 'inside' },
        {
          type: 'slider',
          height: 14,
          bottom: 6,
          borderColor: 'rgba(159,182,204,.2)',
          backgroundColor: 'rgba(9,20,32,.6)',
          fillerColor: 'rgba(18,215,255,.15)'
        }
      ],
      series: [
        {
          name: '实绩功率',
          type: 'line',
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 2.2, color: '#2dd4bf', type: 'solid' },
          data: actual
        },
        {
          name: '短期预测',
          type: 'line',
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 2, color: '#60a5fa', type: 'dashed' },
          data: shortTerm
        },
        {
          name: '超短期预测',
          type: 'line',
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 2, color: '#fbbf24', type: [8, 4, 2, 4] },
          data: ultraShort,
          markLine: {
            symbol: 'none',
            lineStyle: { color: 'rgba(220,235,250,0.45)', width: 1.5, type: 'dashed' },
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
              color: '#c8dce8',
              fontSize: 11,
              backgroundColor: 'rgba(18,24,39,0.85)',
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
          lineStyle: { width: 1.5, color: '#a78bfa', type: 'solid' },
          areaStyle: { color: 'rgba(167,139,250,0.06)' },
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
  color: #7a96aa;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(136, 186, 217, 0.15);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.range-btn:hover {
  color: #9fc4df;
  border-color: rgba(18, 215, 255, 0.3);
}

.range-btn.active {
  color: #12d7ff;
  background: rgba(18, 215, 255, 0.1);
  border-color: rgba(18, 215, 255, 0.4);
}

.chart-canvas {
  flex: 1;
  min-height: 180px;
}
</style>
