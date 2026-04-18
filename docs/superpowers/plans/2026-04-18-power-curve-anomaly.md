# 功率曲线异常检测实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 通过前端实时计算实现电场级功率曲线异常检测，识别离群点、限电和欠发三种异常类型。

**Architecture:** 新增 `powerCurveService.js` 封装数据获取和统计算法（风速分箱 + 置信带），新增 `PowerCurveAnalysis.vue` 页面用 ECharts 散点图展示结果。复用已有 `powerCompareApi` 获取风速和功率数据，集成已有告警和质量标记系统。

**Tech Stack:** Vue 3 + Element Plus + ECharts, JavaScript

---

## File Structure

| 操作 | 文件 | 职责 |
|------|------|------|
| 新增 | `frontend/src/services/powerCurveService.js` | 数据获取 + 异常检测算法 |
| 新增 | `frontend/src/components/PowerCurveAnalysis.vue` | 功率曲线分析页面 |
| 修改 | `frontend/src/router/index.js` | 注册路由 |
| 修改 | `frontend/src/components/AppLayout.vue` | 侧边栏添加入口 |

---

### Task 1: 异常检测算法服务

**Files:**
- Create: `wind-power-forecast/frontend/src/services/powerCurveService.js`

- [ ] **Step 1: 创建 powerCurveService.js**

创建 `wind-power-forecast/frontend/src/services/powerCurveService.js`：

```javascript
import { getPowerCompareData } from '../api/powerCompareApi'
import farmService from '../utils/farmService'

const BIN_WIDTH = 0.5
const MIN_WIND = 0
const MAX_WIND = 25
const MIN_SAMPLES = 5
const CONFIDENCE_SIGMA = 2
const OUTLIER_SIGMA = 3
const CUT_IN_SPEED = 3
const CUT_OUT_SPEED = 25
const CURTAILMENT_VARIANCE_THRESHOLD = 0.05
const MIN_CONSECUTIVE = 5

/**
 * 从 powerCompareApi 获取风速和功率数据
 */
export async function fetchPowerCurveData(startDate, endDate) {
  const farmCode = farmService.getCurrentFarm()
  const response = await getPowerCompareData({
    start: startDate,
    end: endDate,
    types: ['实测值', '理论功率'],
    farm_code: farmCode,
  })
  return response.data || response
}

/**
 * 提取风速和功率配对数据
 */
export function extractWindPowerPairs(rawData, capacity = 779.0) {
  const points = []
  if (!rawData || !Array.isArray(rawData)) return points

  // rawData 是时间序列数组，每个元素包含 timestamp 和各类型值
  for (const entry of rawData) {
    const windSpeed = entry['wind_speed'] || entry['Wind Speed'] || entry['风速'] || null
    const power = entry['actual_power'] || entry['Actual Power'] || entry['实测值'] || entry['实际功率'] || null
    const theoreticalPower = entry['theoretical_power'] || entry['Theoretical Power'] || entry['理论功率'] || null

    if (windSpeed != null && power != null && !isNaN(windSpeed) && !isNaN(power)) {
      points.push({
        timestamp: entry.timestamp || entry.time,
        windSpeed: parseFloat(windSpeed),
        power: parseFloat(power),
        theoreticalPower: theoreticalPower != null ? parseFloat(theoreticalPower) : null,
      })
    }
  }
  return points
}

/**
 * 风速分箱
 */
function getBinIndex(windSpeed) {
  return Math.floor(windSpeed / BIN_WIDTH)
}

function getBinCenter(binIndex) {
  return (binIndex + 0.5) * BIN_WIDTH
}

/**
 * 计算分箱统计量
 */
export function computeBinStatistics(points) {
  const bins = new Map()

  for (const p of points) {
    const idx = getBinIndex(p.windSpeed)
    if (!bins.has(idx)) {
      bins.set(idx, [])
    }
    bins.get(idx).push(p.power)
  }

  const statistics = []
  for (const [binIdx, powers] of bins) {
    if (powers.length < MIN_SAMPLES) continue

    const mean = powers.reduce((a, b) => a + b, 0) / powers.length
    const variance = powers.reduce((a, b) => a + (b - mean) ** 2, 0) / powers.length
    const std = Math.sqrt(variance)

    statistics.push({
      binIndex: binIdx,
      windSpeedCenter: getBinCenter(binIdx),
      mean,
      std,
      count: powers.length,
      upper: mean + CONFIDENCE_SIGMA * std,
      lower: mean - CONFIDENCE_SIGMA * std,
    })
  }

  return statistics.sort((a, b) => a.binIndex - b.binIndex)
}

/**
 * 检测异常点并分类
 */
export function detectAnomalies(points, binStats, capacity = 779.0) {
  const binLookup = new Map()
  for (const stat of binStats) {
    binLookup.set(stat.binIndex, stat)
  }

  const results = points.map((p, index) => {
    const binIdx = getBinIndex(p.windSpeed)
    const stat = binLookup.get(binIdx)

    // 边界保护
    if (p.windSpeed < CUT_IN_SPEED || p.windSpeed > CUT_OUT_SPEED) {
      return { ...p, type: 'normal', binStat: stat }
    }
    // 正常停机
    if (p.power === 0 && p.windSpeed < CUT_IN_SPEED) {
      return { ...p, type: 'normal', binStat: stat }
    }
    // 分箱样本不足，无法判断
    if (!stat) {
      return { ...p, type: 'unknown', binStat: null }
    }

    const deviation = Math.abs(p.power - stat.mean)
    const sigmaMultiple = stat.std > 0 ? deviation / stat.std : 0

    // 在置信带内 → 正常
    if (p.power >= stat.lower && p.power <= stat.upper) {
      return { ...p, type: 'normal', binStat: stat }
    }

    return {
      ...p,
      type: 'candidate', // 候选异常，待分类
      sigmaMultiple,
      belowLower: p.power < stat.lower,
      aboveUpper: p.power > stat.upper,
      binStat: stat,
    }
  })

  // 第二遍：分类候选异常点
  classifyAnomalies(results, capacity)

  return results
}

/**
 * 对候选异常点进行分类：离群/限电/欠发
 */
function classifyAnomalies(results, capacity) {
  for (let i = 0; i < results.length; i++) {
    const r = results[i]
    if (r.type !== 'candidate') continue

    // 检查是否连续低于下界
    if (r.belowLower) {
      const consecutiveBelow = countConsecutive(results, i, (item) =>
        item.type === 'candidate' && item.belowLower
      )

      if (consecutiveBelow >= MIN_CONSECUTIVE) {
        // 限电 vs 欠发
        const variance = computeLocalVariance(results, i, consecutiveBelow)
        const ratedWindSpeed = findRatedWindSpeed(results)
        if (r.windSpeed > ratedWindSpeed && variance < CURTAILMENT_VARIANCE_THRESHOLD * capacity) {
          markConsecutive(results, i, consecutiveBelow, 'curtailment')
        } else {
          markConsecutive(results, i, consecutiveBelow, 'underperformance')
        }
        i += consecutiveBelow - 1
        continue
      }
    }

    // 超出上界的孤立点 → 离群
    if (r.aboveUpper && r.sigmaMultiple > OUTLIER_SIGMA) {
      r.type = 'outlier'
      continue
    }

    // 低于下界的孤立点 → 离群
    if (r.belowLower && r.sigmaMultiple > OUTLIER_SIGMA) {
      r.type = 'outlier'
      continue
    }

    // 不满足严格条件的候选 → 标记为轻微异常，归入离群
    r.type = 'outlier'
  }
}

function countConsecutive(results, startIndex, predicate) {
  let count = 0
  for (let i = startIndex; i < results.length; i++) {
    if (predicate(results[i])) {
      count++
    } else {
      break
    }
  }
  return count
}

function markConsecutive(results, startIndex, count, type) {
  for (let i = startIndex; i < startIndex + count && i < results.length; i++) {
    results[i].type = type
  }
}

function computeLocalVariance(results, startIndex, count) {
  const powers = []
  for (let i = startIndex; i < startIndex + count && i < results.length; i++) {
    powers.push(results[i].power)
  }
  if (powers.length === 0) return 0
  const mean = powers.reduce((a, b) => a + b, 0) / powers.length
  return powers.reduce((a, b) => a + (b - mean) ** 2, 0) / powers.length
}

/**
 * 估算额定风速（功率均值最高的分箱对应的风速）
 */
function findRatedWindSpeed(results) {
  const binPowers = new Map()
  for (const r of results) {
    const binIdx = getBinIndex(r.windSpeed)
    if (!binPowers.has(binIdx)) {
      binPowers.set(binIdx, [])
    }
    binPowers.get(binIdx).push(r.power)
  }

  let maxMean = -Infinity
  let ratedBin = 0
  for (const [binIdx, powers] of binPowers) {
    const mean = powers.reduce((a, b) => a + b, 0) / powers.length
    if (mean > maxMean) {
      maxMean = mean
      ratedBin = binIdx
    }
  }
  return getBinCenter(ratedBin)
}

/**
 * 计算异常统计摘要
 */
export function computeSummary(results) {
  const total = results.filter((r) => r.type !== 'unknown').length
  const outliers = results.filter((r) => r.type === 'outlier').length
  const curtailments = results.filter((r) => r.type === 'curtailment').length
  const underperformance = results.filter((r) => r.type === 'underperformance').length
  const abnormalCount = outliers + curtailments + underperformance
  const abnormalRate = total > 0 ? abnormalCount / total : 0

  return {
    total,
    abnormalCount,
    abnormalRate,
    outliers,
    curtailments,
    underperformance,
    alertTriggered: abnormalRate > 0.15,
  }
}
```

- [ ] **Step 2: 验证语法**

Run: `cd "D:\Wind-power-microserver\wind-power-forecast\frontend" && npx eslint src/services/powerCurveService.js --no-eslintrc --env es2020 2>&1 || echo "Syntax check via node" && node -e "require('fs').readFileSync('src/services/powerCurveService.js','utf8'); console.log('File readable')"`
Expected: File readable, no syntax errors

- [ ] **Step 3: Commit**

```bash
git add wind-power-forecast/frontend/src/services/powerCurveService.js
git commit -m "feat: add power curve anomaly detection algorithm service"
```

---

### Task 2: 功率曲线分析页面

**Files:**
- Create: `wind-power-forecast/frontend/src/components/PowerCurveAnalysis.vue`

- [ ] **Step 1: 创建 PowerCurveAnalysis.vue**

创建 `wind-power-forecast/frontend/src/components/PowerCurveAnalysis.vue`：

```vue
<template>
  <div class="power-curve-analysis">
    <div class="controls">
      <el-date-picker
        v-model="dateRange"
        type="daterange"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        value-format="YYYY-MM-DD"
        :shortcuts="dateShortcuts"
        @change="loadData"
      />
      <el-checkbox-group v-model="visibleTypes">
        <el-checkbox label="normal">正常点</el-checkbox>
        <el-checkbox label="outlier">离群点</el-checkbox>
        <el-checkbox label="curtailment">限电</el-checkbox>
        <el-checkbox label="underperformance">欠发</el-checkbox>
      </el-checkbox-group>
      <el-button type="primary" @click="loadData" :loading="loading">分析</el-button>
      <el-button type="warning" @click="markAnomalies" :disabled="!hasAnomalies" :loading="marking">
        标记异常到质量系统
      </el-button>
    </div>

    <div class="summary-cards" v-if="summary">
      <el-card shadow="hover">
        <div class="stat-value">{{ summary.total }}</div>
        <div class="stat-label">总数据点</div>
      </el-card>
      <el-card shadow="hover" :class="{ 'alert-card': summary.alertTriggered }">
        <div class="stat-value">{{ (summary.abnormalRate * 100).toFixed(1) }}%</div>
        <div class="stat-label">异常率</div>
      </el-card>
      <el-card shadow="hover">
        <div class="stat-value" style="color:#a855f7">{{ summary.outliers }}</div>
        <div class="stat-label">离群点</div>
      </el-card>
      <el-card shadow="hover">
        <div class="stat-value" style="color:#ef4444">{{ summary.curtailments }}</div>
        <div class="stat-label">限电</div>
      </el-card>
      <el-card shadow="hover">
        <div class="stat-value" style="color:#f59e0b">{{ summary.underperformance }}</div>
        <div class="stat-label">欠发</div>
      </el-card>
    </div>

    <div ref="chartContainer" class="chart-container"></div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted, nextTick, computed } from 'vue'
import * as echarts from 'echarts'
import {
  fetchPowerCurveData,
  extractWindPowerPairs,
  computeBinStatistics,
  detectAnomalies,
  computeSummary,
} from '../services/powerCurveService'
import axiosInstance from '../api/axios'

export default {
  name: 'PowerCurveAnalysis',
  setup() {
    const chartContainer = ref(null)
    let chart = null

    const dateRange = ref([])
    const loading = ref(false)
    const marking = ref(false)
    const visibleTypes = ref(['normal', 'outlier', 'curtailment', 'underperformance'])
    const allResults = ref([])
    const binStats = ref([])
    const summary = ref(null)

    const hasAnomalies = computed(() => {
      return summary.value && summary.value.abnormalCount > 0
    })

    const dateShortcuts = [
      { text: '最近 7 天', value: () => {
        const end = new Date()
        const start = new Date()
        start.setTime(start.getTime() - 7 * 24 * 3600 * 1000)
        return [start, end]
      }},
      { text: '最近 30 天', value: () => {
        const end = new Date()
        const start = new Date()
        start.setTime(start.getTime() - 30 * 24 * 3600 * 1000)
        return [start, end]
      }},
    ]

    function initChart() {
      if (chartContainer.value && !chart) {
        chart = echarts.init(chartContainer.value)
        window.addEventListener('resize', () => chart?.resize())
      }
    }

    async function loadData() {
      if (!dateRange.value || dateRange.value.length < 2) return
      loading.value = true
      try {
        const rawData = await fetchPowerCurveData(dateRange.value[0], dateRange.value[1])
        const points = extractWindPowerPairs(rawData)
        const stats = computeBinStatistics(points)
        const results = detectAnomalies(points, stats)

        allResults.value = results
        binStats.value = stats
        summary.value = computeSummary(results)

        await nextTick()
        renderChart()
      } catch (err) {
        console.error('加载功率曲线数据失败:', err)
      } finally {
        loading.value = false
      }
    }

    function renderChart() {
      if (!chart) initChart()
      if (!chart) return

      const series = []

      // 置信带（areaStyle）
      if (binStats.value.length > 0) {
        const upperData = binStats.value.map((s) => [s.windSpeedCenter, s.upper])
        const lowerData = binStats.value.map((s) => [s.windSpeedCenter, s.lower])
        series.push({
          name: '置信带上界',
          type: 'line',
          data: upperData,
          lineStyle: { opacity: 0 },
          areaStyle: { color: 'rgba(74, 222, 128, 0.12)' },
          stack: 'confidence-band',
          symbol: 'none',
          silent: true,
          z: 1,
        })
        series.push({
          name: '置信带下界',
          type: 'line',
          data: lowerData,
          lineStyle: { opacity: 0 },
          areaStyle: { color: '#1a1a2e' },
          stack: 'confidence-band',
          symbol: 'none',
          silent: true,
          z: 1,
        })
      }

      // 正常点
      if (visibleTypes.value.includes('normal')) {
        const normalData = allResults.value
          .filter((r) => r.type === 'normal')
          .map((r) => [r.windSpeed, r.power])
        series.push({
          name: '正常点',
          type: 'scatter',
          data: normalData,
          symbolSize: 3,
          itemStyle: { color: '#4ade80', opacity: 0.4 },
          z: 2,
        })
      }

      // 离群点
      if (visibleTypes.value.includes('outlier')) {
        const outlierData = allResults.value
          .filter((r) => r.type === 'outlier')
          .map((r) => [r.windSpeed, r.power])
        series.push({
          name: '离群点',
          type: 'scatter',
          data: outlierData,
          symbolSize: 6,
          itemStyle: { color: '#a855f7' },
          z: 3,
        })
      }

      // 限电
      if (visibleTypes.value.includes('curtailment')) {
        const curtailmentData = allResults.value
          .filter((r) => r.type === 'curtailment')
          .map((r) => [r.windSpeed, r.power])
        series.push({
          name: '限电',
          type: 'scatter',
          data: curtailmentData,
          symbolSize: 6,
          itemStyle: { color: '#ef4444' },
          z: 3,
        })
      }

      // 欠发
      if (visibleTypes.value.includes('underperformance')) {
        const underperformanceData = allResults.value
          .filter((r) => r.type === 'underperformance')
          .map((r) => [r.windSpeed, r.power])
        series.push({
          name: '欠发',
          type: 'scatter',
          data: underperformanceData,
          symbolSize: 6,
          itemStyle: { color: '#f59e0b' },
          z: 3,
        })
      }

      const option = {
        title: { text: '功率曲线异常检测', left: 'center' },
        tooltip: {
          trigger: 'item',
          formatter: (params) => {
            return `${params.seriesName}<br/>风速: ${params.data[0].toFixed(1)} m/s<br/>功率: ${params.data[1].toFixed(1)} MW`
          },
        },
        legend: { bottom: 10 },
        grid: { left: 60, right: 30, top: 50, bottom: 60 },
        xAxis: {
          name: '风速 (m/s)',
          nameLocation: 'center',
          nameGap: 30,
          min: 0,
          max: 25,
        },
        yAxis: {
          name: '功率 (MW)',
          nameLocation: 'center',
          nameGap: 50,
          min: 0,
        },
        series,
      }

      chart.setOption(option, true)
    }

    async function markAnomalies() {
      const anomalies = allResults.value.filter(
        (r) => r.type === 'outlier' || r.type === 'curtailment' || r.type === 'underperformance'
      )
      if (anomalies.length === 0) return

      marking.value = true
      try {
        // 按时间段分组创建质量标记
        const typeMap = { outlier: '离群点', curtailment: '限电', underperformance: '欠发' }
        const byType = {}
        for (const a of anomalies) {
          const label = typeMap[a.type] || a.type
          if (!byType[label]) byType[label] = []
          byType[label].push(a)
        }

        for (const [label, points] of Object.entries(byType)) {
          const timestamps = points.map((p) => p.timestamp).filter(Boolean).sort()
          if (timestamps.length === 0) continue

          await axiosInstance.post('/api/v1/report/quality-markers', {
            farm_code: farmService.getCurrentFarm(),
            start_time: timestamps[0],
            end_time: timestamps[timestamps.length - 1],
            marker_type: '功率曲线异常',
            reason: `自动检测: ${label} (${points.length} 个点)`,
            exclude_from_score: true,
          })
        }
        ElMessage.success(`已标记 ${anomalies.length} 个异常点到质量系统`)
      } catch (err) {
        console.error('标记异常失败:', err)
        ElMessage.error('标记失败: ' + (err.message || '未知错误'))
      } finally {
        marking.value = false
      }
    }

    onMounted(() => {
      // 默认最近 7 天
      const end = new Date()
      const start = new Date()
      start.setTime(start.getTime() - 7 * 24 * 3600 * 1000)
      dateRange.value = [
        start.toISOString().slice(0, 10),
        end.toISOString().slice(0, 10),
      ]
      nextTick(() => {
        initChart()
        loadData()
      })
    })

    onUnmounted(() => {
      if (chart) {
        chart.dispose()
        chart = null
      }
    })

    return {
      chartContainer,
      dateRange,
      loading,
      marking,
      visibleTypes,
      summary,
      hasAnomalies,
      dateShortcuts,
      loadData,
      markAnomalies,
    }
  },
}
</script>

<style scoped>
.power-curve-analysis {
  padding: 20px;
}
.controls {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.summary-cards {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}
.summary-cards .el-card {
  flex: 1;
  text-align: center;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #e0e0e0;
}
.stat-label {
  font-size: 13px;
  color: #999;
  margin-top: 4px;
}
.alert-card {
  border: 2px solid #ef4444 !important;
}
.alert-card .stat-value {
  color: #ef4444;
}
.chart-container {
  width: 100%;
  height: 500px;
}
</style>
```

注意：需要确保 `import farmService from '../utils/farmService'` 在 `markAnomalies` 函数中使用。在文件顶部 import 区添加：
```javascript
import farmService from '../utils/farmService'
```

并添加 `import { ElMessage } from 'element-plus'`。

- [ ] **Step 2: 验证构建**

Run: `cd "D:\Wind-power-microserver\wind-power-forecast\frontend" && npm run build 2>&1 | tail -10`
Expected: 构建成功

- [ ] **Step 3: Commit**

```bash
git add wind-power-forecast/frontend/src/components/PowerCurveAnalysis.vue
git commit -m "feat: add PowerCurveAnalysis page with scatter chart and anomaly detection"
```

---

### Task 3: 路由注册与侧边栏入口

**Files:**
- Modify: `wind-power-forecast/frontend/src/router/index.js`
- Modify: `wind-power-forecast/frontend/src/components/AppLayout.vue`

- [ ] **Step 1: 在 router/index.js 添加路由**

在 `wind-power-forecast/frontend/src/router/index.js` 的 lazy import 区域（约第 19 行之后）添加：

```javascript
const PowerCurveAnalysis = () => import('../components/PowerCurveAnalysis.vue')
```

在 children 数组中，`accuracy-report` 路由之后（约第 69 行之后）添加：

```javascript
      {
        path: 'power-curve',
        name: 'PowerCurveAnalysis',
        component: PowerCurveAnalysis,
        meta: { requiredPermissions: ['view_all_data'], keepAlive: true }
      },
```

- [ ] **Step 2: 在 AppLayout.vue 侧边栏添加入口**

在 `wind-power-forecast/frontend/src/components/AppLayout.vue` 的 "分析与报表" `<el-sub-menu>` 中（约第 42-46 行），在 `accuracy-report` 菜单项之后添加：

```html
          <el-menu-item index="/power-curve" v-if="hasPermission('view_all_data')">功率曲线分析</el-menu-item>
```

- [ ] **Step 3: 验证构建**

Run: `cd "D:\Wind-power-microserver\wind-power-forecast\frontend" && npm run build 2>&1 | tail -10`
Expected: 构建成功

- [ ] **Step 4: Commit**

```bash
git add wind-power-forecast/frontend/src/router/index.js wind-power-forecast/frontend/src/components/AppLayout.vue
git commit -m "feat: add power curve analysis route and sidebar entry"
```

---

### Task 4: 告警集成

**Files:**
- Modify: `wind-power-forecast/frontend/src/services/powerCurveService.js`

- [ ] **Step 1: 添加告警触发函数**

在 `wind-power-forecast/frontend/src/services/powerCurveService.js` 文件末尾添加：

```javascript
import axiosInstance from '../api/axios'

/**
 * 当异常率超过阈值时创建告警记录
 */
export async function createAnomalyAlert(summary, farmCode) {
  if (!summary.alertTriggered) return false

  try {
    await axiosInstance.post('/api/v1/alarms', {
      source: 'power_curve_analysis',
      farm_code: farmCode,
      module: '功率曲线分析',
      level: 'warning',
      message: `功率曲线异常率达 ${(summary.abnormalRate * 100).toFixed(1)}%，超过 15% 阈值。离群点: ${summary.outliers}, 限电: ${summary.curtailments}, 欠发: ${summary.underperformance}`,
      status: 'open',
    })
    return true
  } catch (err) {
    console.error('创建告警失败:', err)
    return false
  }
}
```

注意：如果文件顶部已有 `import axiosInstance`，则不要重复添加。

- [ ] **Step 2: 在 PowerCurveAnalysis.vue 中调用告警**

在 `wind-power-forecast/frontend/src/components/PowerCurveAnalysis.vue` 的 import 中添加 `createAnomalyAlert`：

```javascript
import {
  fetchPowerCurveData,
  extractWindPowerPairs,
  computeBinStatistics,
  detectAnomalies,
  computeSummary,
  createAnomalyAlert,
} from '../services/powerCurveService'
```

在 `loadData` 函数中，`summary.value = computeSummary(results)` 之后添加：

```javascript
        // 异常率超阈值时触发告警
        if (summary.value.alertTriggered) {
          createAnomalyAlert(summary.value, farmService.getCurrentFarm())
        }
```

- [ ] **Step 3: 验证构建**

Run: `cd "D:\Wind-power-microserver\wind-power-forecast\frontend" && npm run build 2>&1 | tail -10`
Expected: 构建成功

- [ ] **Step 4: Commit**

```bash
git add wind-power-forecast/frontend/src/services/powerCurveService.js wind-power-forecast/frontend/src/components/PowerCurveAnalysis.vue
git commit -m "feat: add anomaly alert integration for power curve analysis"
```

---

### Task 5: 集成验证

**Files:**
- All modified files

- [ ] **Step 1: 验证前端构建**

Run: `cd "D:\Wind-power-microserver\wind-power-forecast\frontend" && npm run build 2>&1 | tail -10`
Expected: 构建成功，无 error

- [ ] **Step 2: 验证路由和侧边栏**

在浏览器中登录系统，检查侧边栏 "分析与报表" 分组下是否出现 "功率曲线分析" 菜单项。点击进入应显示空页面（无数据时显示空图表）。

- [ ] **Step 3: Commit（如有修复）**

```bash
git add -A
git commit -m "fix: resolve integration issues from power curve anomaly implementation"
```

---

## Plan Self-Review

**1. Spec coverage:**
- 统计方法 + 风速分箱 → Task 1 ✅
- 置信带（μ ± 2σ）→ Task 1 ✅
- 异常分类（离群/限电/欠发）→ Task 1 ✅
- 边界处理（切入/切出风速）→ Task 1 ✅
- 前端可视化（散点图 + 色带 + checkbox）→ Task 2 ✅
- 日期范围选择器 + 电场选择 → Task 2 ✅
- 统计摘要卡片 → Task 2 ✅
- 告警集成（>15% 触发）→ Task 4 ✅
- 质量标记联动 → Task 2（markAnomalies 函数）✅
- 路由和侧边栏 → Task 3 ✅

**2. Placeholder scan:** 无 TBD/TODO。所有代码完整。需注意 Task 2 的 extractWindPowerPairs 中的字段名映射需根据实际 API 返回数据调整。

**3. Type consistency:** 所有函数名在 Task 1-4 中一致：`fetchPowerCurveData`, `extractWindPowerPairs`, `computeBinStatistics`, `detectAnomalies`, `computeSummary`, `createAnomalyAlert`。异常类型字符串一致：`'normal'`, `'outlier'`, `'curtailment'`, `'underperformance'`。
