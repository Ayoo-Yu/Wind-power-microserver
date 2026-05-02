
<template>
  <div class="power-compare-container power-predict-container page-shell">
    <h1 class="page-title">功率对比与考核分析</h1>

    <el-tabs v-model="analysisTab" class="analysis-tabs">
      <el-tab-pane label="单站深度分析" name="single" />
      <el-tab-pane label="多站横向对比" name="fleet" />
    </el-tabs>

    <div class="summary-grid">
      <el-card class="summary-card" v-for="(card, idx) in kpiCards" :key="idx">
        <div class="summary-label">{{ card.label }}</div>
        <div class="summary-value" :class="{ 'summary-warning': idx === 3 }">{{ card.value }}</div>
      </el-card>
    </div>

    <el-card class="control-card">
      <div class="group-title">步骤一：数据范围定义</div>
      <div class="control-row">
        <el-select v-if="analysisTab === 'single'" v-model="singleFarmCode" filterable class="farm-select" placeholder="选择场站">
          <el-option v-for="farm in fleetCompareFarms" :key="farm.code" :label="`${farm.name} (${farm.code})`" :value="farm.code" />
        </el-select>
        <el-select v-else v-model="fleetCompareFarmCodes" multiple collapse-tags filterable class="farm-select" placeholder="选择多个场站">
          <el-option v-for="farm in fleetCompareFarms" :key="farm.code" :label="`${farm.name} (${farm.code})`" :value="farm.code" />
        </el-select>

        <el-date-picker
          v-model="timeRange"
          type="datetimerange"
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          value-format="YYYY-MM-DD HH:mm:ss"
          class="time-range-picker"
        />

        <el-button-group>
          <el-button type="info" plain size="small" @click="setQuickTimeRange('today')">今日</el-button>
          <el-button type="info" plain size="small" @click="setQuickTimeRange('3d')">近三天</el-button>
          <el-button type="info" plain size="small" @click="setQuickTimeRange('1w')">近一周</el-button>
        </el-button-group>

        <el-button type="primary" :loading="loading" class="query-btn" @click="fetchComparisonData">查询</el-button>
      </div>

      <div class="group-title">步骤二：图表展示控制</div>
      <div class="control-row">
        <el-checkbox-group v-model="selectedTypes">
          <el-checkbox label="实测值" />
          <el-checkbox label="超短期预测" />
          <el-checkbox label="短期预测" />
          <el-checkbox label="中期预测" />
          <el-checkbox label="短期风速预测" />
          <el-checkbox label="中期风速预测" />
          <el-checkbox label="短期预测区间" />
          <el-checkbox label="超短期预测区间" />
          <el-checkbox label="中期预测区间" />
        </el-checkbox-group>
        <el-switch v-model="showCurtailmentTag" active-text="显示限电标识" />
      </div>

      <div class="group-title">步骤三：数据与报表导出</div>
      <el-dropdown @command="handleExportCommand">
        <el-button type="success">
          📥 导出报表
          <el-icon class="el-icon--right"><Download /></el-icon>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="raw_csv">导出原始数据(CSV)</el-dropdown-item>
            <el-dropdown-item command="metrics_excel">导出考核指标(Excel)</el-dropdown-item>
            <el-dropdown-item command="chart_png">导出图表(PNG)</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </el-card>

    <div v-if="analysisTab === 'single'" class="single-chart-section">
      <el-card class="chart-card force-chart-card">
        <template #header><div class="card-header">主曲线（双Y轴）</div></template>
        <div class="series-legend">
          <button
            v-for="item in curveLegendItems"
            :key="item.name"
            type="button"
            class="legend-toggle"
            :class="{ inactive: !isCurveLegendActive(item.name) }"
            @click="toggleSelectedType(item.name)"
          >
            <span class="legend-swatch" :style="{ backgroundColor: item.color }"></span>
            <span>{{ item.name }}</span>
          </button>
        </div>
        <div class="chart-wrapper" ref="mainChartEl">
          <canvas ref="mainChartCanvas" class="native-chart-canvas" @mousemove="handleChartMouseMove($event, 'main')" @mouseleave="hideChartTooltip"></canvas>
        </div>
      </el-card>
      <el-card class="chart-card force-chart-card">
        <template #header><div class="card-header">误差曲线（预测值减实测值）</div></template>
        <div class="chart-wrapper small" ref="errorChartEl">
          <canvas ref="errorChartCanvas" class="native-chart-canvas" @mousemove="handleChartMouseMove($event, 'error')" @mouseleave="hideChartTooltip"></canvas>
        </div>
      </el-card>
    </div>

    <div v-else>
      <el-card class="chart-card" v-if="fleetCompareRows.length > 0">
        <template #header><div class="card-header">多站准确率对比（短期 vs 超短期）</div></template>
        <div class="chart-wrapper" ref="fleetBarChartEl">
          <canvas ref="fleetBarChartCanvas" class="native-chart-canvas" @mousemove="handleChartMouseMove($event, 'fleet')" @mouseleave="hideChartTooltip"></canvas>
        </div>
      </el-card>
      <el-card class="chart-card" v-if="fleetCompareRows.length > 0">
        <template #header><div class="card-header">多场站详细指标表</div></template>
        <el-table :data="fleetCompareRows" border size="small">
          <el-table-column prop="farm_name" label="场站名称" min-width="160" />
          <el-table-column prop="farm_code" label="场站编码" min-width="130" />
          <el-table-column label="短期准确率(%)" width="130"><template #default="scope">{{ formatPct(scope.row.short_acc) }}</template></el-table-column>
          <el-table-column label="短期合格率(%)" width="130"><template #default="scope">{{ formatPct(scope.row.short_qualified_rate) }}</template></el-table-column>
          <el-table-column label="超短期准确率(%)" width="140"><template #default="scope">{{ formatPct(scope.row.supershort_acc) }}</template></el-table-column>
          <el-table-column label="超短期合格率(%)" width="140"><template #default="scope">{{ formatPct(scope.row.supershort_qualified_rate) }}</template></el-table-column>
          <el-table-column label="RMSE" width="110"><template #default="scope">{{ formatNum(scope.row.rmse_avg) }}</template></el-table-column>
          <el-table-column label="MAE" width="110"><template #default="scope">{{ formatNum(scope.row.mae_avg) }}</template></el-table-column>
          <el-table-column prop="unqualified_points" label="不合格点数" width="120" />
        </el-table>
      </el-card>
    </div>

    <div class="empty-data-container" v-if="!loading && showEmptyState">
      <el-card class="empty-data-card"><div class="empty-data-content"><h3>暂无数据</h3><p>请选择时间范围并点击“查询”。</p></div></el-card>
    </div>

    <div v-if="chartTooltip.visible" class="chart-tooltip" :style="{ left: `${chartTooltip.x}px`, top: `${chartTooltip.y}px` }">
      <div v-for="(line, index) in chartTooltip.lines" :key="index">{{ line }}</div>
    </div>

    <LoadingIndicator :visible="loading" message="数据加载中..." />
  </div>
</template>

<script>
import { Download } from '@element-plus/icons-vue'
import farmService from '../utils/farmService'
import { getFleetMetrics, getPowerCompareData } from '../api/powerCompareApi'
import LoadingIndicator from './LoadingIndicator.vue'

const YAXIS_POWER = 0
const YAXIS_WINDSPEED = 1

export default {
  name: 'PowerCompare',
  components: { LoadingIndicator, Download },
  data() {
    return {
      analysisTab: 'single',
      timeRange: [],
      loading: false,
      chartData: null,
      fleetCompareFarms: [],
      singleFarmCode: '',
      fleetCompareFarmCodes: [],
      selectedTypes: ['实测值', '超短期预测', '短期预测', '中期预测', '短期风速预测', '中期风速预测'],
      showCurtailmentTag: true,
      installedCapacity: 779.0,
      mainChart: null,
      errorChart: null,
      fleetBarChart: null,
      chartDisposed: false,
      fetchSeq: 0,
      chartRenderRaf: null,
      chartRenderTimers: [],
      chartRenderSeq: 0,
      chartResizeObserver: null,
      observedChartEls: [],
      chartMeta: {},
      chartTooltip: { visible: false, x: 0, y: 0, lines: [] },
      exportData: { comparison: null, metrics: null },
      singleSeriesState: null,
      singleMetricsSummary: {
        shortAcc: null,
        shortQualifiedRate: null,
        supershortAcc: null,
        supershortQualifiedRate: null,
        rmse: null,
        mae: null,
        unqualifiedPoints: 0,
        assessmentEnergy: 0
      },
      fleetCompareRows: []
    }
  },
  computed: {
    hasSingleChartData() {
      const labels = this.exportData.comparison?.labels || []
      const datasets = this.exportData.comparison?.datasets || {}
      const visibleNames = ['实测值', '超短期预测', '短期预测', '中期预测', '短期风速预测', '中期风速预测']
      return labels.length > 0 && visibleNames.some(name => this.hasSeriesValue(datasets[name]))
    },
    showEmptyState() {
      return this.analysisTab === 'single' ? !this.hasSingleChartData : this.fleetCompareRows.length === 0
    },
    kpiCards() {
      if (this.analysisTab === 'single') {
        return [
          { label: '短期预测指标', value: `准确率 ${this.formatPct(this.singleMetricsSummary.shortAcc)} | 合格率 ${this.formatPct(this.singleMetricsSummary.shortQualifiedRate)}` },
          { label: '超短期预测指标', value: `准确率 ${this.formatPct(this.singleMetricsSummary.supershortAcc)} | 合格率 ${this.formatPct(this.singleMetricsSummary.supershortQualifiedRate)}` },
          { label: '误差统计 (RMSE/MAE)', value: `RMSE ${this.formatNum(this.singleMetricsSummary.rmse)} | MAE ${this.formatNum(this.singleMetricsSummary.mae)}` },
          { label: '损失/受累电量评估', value: `不合格点 ${this.singleMetricsSummary.unqualifiedPoints} | 考核电量 ${this.formatNum(this.singleMetricsSummary.assessmentEnergy)} MWh` }
        ]
      }
      const rows = this.fleetCompareRows
      const avgShort = this.mean(rows.map(v => v.short_acc))
      const avgUltra = this.mean(rows.map(v => v.supershort_acc))
      const avgRmse = this.mean(rows.map(v => v.rmse_avg))
      const totalUnqualified = rows.reduce((s, r) => s + (Number(r.unqualified_points) || 0), 0)
      return [
        { label: '参与场站数', value: `${rows.length}` },
        { label: '短期平均准确率', value: this.formatPct(avgShort) },
        { label: '超短期平均准确率', value: this.formatPct(avgUltra) },
        { label: 'RMSE/不合格点', value: `${this.formatNum(avgRmse)} / ${totalUnqualified}` }
      ]
    },
    curveLegendItems() {
      return [
        { name: '实测值', color: '#fb7185' },
        { name: '超短期预测', color: '#22d3ee' },
        { name: '短期预测', color: '#60a5fa' },
        { name: '中期预测', color: '#4ade80' },
        { name: '短期风速预测', color: '#fbbf24' },
        { name: '中期风速预测', color: '#c084fc' }
      ]
    }
  },
  async mounted() {
    const now = new Date()
    const fmt = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    this.timeRange = [`${fmt(now)} 00:00:00`, `${fmt(now)} 23:59:59`]
    await this.loadFleetCompareFarms()
    const currentFarm = farmService.getCurrentFarm()
    this.singleFarmCode = this.fleetCompareFarms.some(f => f.code === currentFarm)
      ? currentFarm
      : (this.fleetCompareFarms[0]?.code || '')
    this.updateInstalledCapacity(this.singleFarmCode)
    this.fleetCompareFarmCodes = this.fleetCompareFarms.map(v => v.code)
    this.applyRouteQuery()
    farmService.addListener(this.handleFarmChanged)
    this.fetchComparisonData()
    window.addEventListener('resize', this.resizeCharts)
  },
  beforeUnmount() {
    this.chartDisposed = true
    farmService.removeListener(this.handleFarmChanged)
    window.removeEventListener('resize', this.resizeCharts)
    if (this.chartRenderRaf) {
      cancelAnimationFrame(this.chartRenderRaf)
      this.chartRenderRaf = null
    }
    this.clearScheduledChartRender()
    if (this.chartResizeObserver) {
      this.chartResizeObserver.disconnect()
      this.chartResizeObserver = null
    }
    this.observedChartEls = []
    this.destroyAllCharts()
  },
  methods: {
    handleFarmChanged(code) {
      if (this.analysisTab === 'single') {
        const validCode = this.fleetCompareFarms.some(f => f.code === code) ? code : (this.fleetCompareFarms[0]?.code || '')
        this.singleFarmCode = validCode
        this.updateInstalledCapacity(validCode)
        this.fetchComparisonData()
      }
    },
    updateInstalledCapacity(farmCode) {
      const farm = this.fleetCompareFarms.find(f => f.code === farmCode)
      if (farm && farm.capacity > 0) this.installedCapacity = farm.capacity
    },
    applyRouteQuery() {
      const query = this.$route?.query || {}
      const mode = typeof query.mode === 'string' ? query.mode : ''
      const farmCode = typeof query.farm_code === 'string' ? query.farm_code : ''
      const farmCodes = typeof query.farm_codes === 'string' ? query.farm_codes.split(',').map(v => v.trim()).filter(Boolean) : []
      const start = typeof query.start === 'string' ? query.start : ''
      const end = typeof query.end === 'string' ? query.end : ''
      const predictionType = typeof query.prediction_type === 'string' ? query.prediction_type.toLowerCase() : ''
      const view = typeof query.view === 'string' ? query.view : ''

      if (mode === 'fleet' || mode === 'single') this.analysisTab = mode
      if (farmCode && this.fleetCompareFarms.some(v => v.code === farmCode)) this.singleFarmCode = farmCode
      if (farmCodes.length) {
        this.fleetCompareFarmCodes = farmCodes.filter(code => this.fleetCompareFarms.some(v => v.code === code))
      }
      if (start && end) this.timeRange = [start, end]

      if (predictionType.includes('super')) {
        this.selectedTypes = ['实测值', '超短期预测']
      } else if (predictionType.includes('short')) {
        this.selectedTypes = ['实测值', '短期预测']
      }
    },
    syncRouteQuery() {
      const query = {
        mode: this.analysisTab,
        start: this.timeRange?.[0] || undefined,
        end: this.timeRange?.[1] || undefined
      }

      if (this.analysisTab === 'single') {
        query.farm_code = this.singleFarmCode || undefined
        query.farm_codes = undefined
      } else {
        query.farm_code = undefined
        query.farm_codes = this.fleetCompareFarmCodes?.length ? this.fleetCompareFarmCodes.join(',') : undefined
        query.view = undefined
      }

      this.$router.replace({
        query: {
          ...this.$route.query,
          ...query
        }
      })
    },
    async loadFleetCompareFarms() {
      const farms = await farmService.loadAvailableFarms(true)
      this.fleetCompareFarms = (Array.isArray(farms) ? farms : [])
        .filter(f => f && f.code)
        .map(f => ({ code: f.code, name: f.name || f.code, capacity: Number(f.capacity) || 0 }))
    },
    formatPct(value) {
      if (!Number.isFinite(Number(value))) return '--'
      return `${Number(value).toFixed(2)}%`
    },
    formatNum(value) {
      if (!Number.isFinite(Number(value))) return '--'
      return Number(value).toFixed(2)
    },
    mean(values) {
      const arr = values.map(Number).filter(Number.isFinite)
      if (!arr.length) return null
      return arr.reduce((s, v) => s + v, 0) / arr.length
    },
    toggleSelectedType(type) {
      if (!type) return
      if (this.selectedTypes.includes(type)) {
        this.selectedTypes = this.selectedTypes.filter(item => item !== type)
      } else {
        this.selectedTypes = [...this.selectedTypes, type]
      }
    },
    isCurveLegendActive(type) {
      return this.selectedTypes.includes(type)
    },
    getWindDirectionArrow(deg) {
      const d = Number(deg)
      if (!Number.isFinite(d)) return ''
      const normalized = ((d % 360) + 360) % 360
      const arrows = ['↑', '↗', '→', '↘', '↓', '↙', '←', '↖']
      return arrows[Math.round(normalized / 45) % 8]
    },
    resizeCharts() {
      if (this.chartDisposed) return
      if (this.analysisTab === 'single' && this.hasSingleChartData) this.scheduleChartRender('single')
      if (this.analysisTab === 'fleet' && this.fleetCompareRows.length) this.scheduleChartRender('fleet')
    },
    isChartElementReady(el) {
      if (!el) return false
      const rect = el.getBoundingClientRect()
      return rect.width > 0 && rect.height > 0
    },
    observeChartElement(el) {
      if (!el || typeof ResizeObserver === 'undefined') return
      if (!this.chartResizeObserver) {
        this.chartResizeObserver = new ResizeObserver(() => {
          if (this.chartDisposed) return
          this.resizeCharts()
          if (this.analysisTab === 'single' && this.singleSeriesState) this.scheduleChartRender('single')
          if (this.analysisTab === 'fleet' && this.fleetCompareRows.length) this.scheduleChartRender('fleet')
        })
      }
      if (!this.observedChartEls.includes(el)) {
        this.chartResizeObserver.observe(el)
        this.observedChartEls.push(el)
      }
    },
    scheduleChartRender(mode = 'single', attempts = 0) {
      if (this.chartDisposed) return
      this.clearScheduledChartRender()
      const renderSeq = ++this.chartRenderSeq
      this.$nextTick(() => {
        if (this.chartDisposed || renderSeq !== this.chartRenderSeq || mode !== this.analysisTab) return
        this.chartRenderRaf = requestAnimationFrame(() => {
          this.chartRenderRaf = null
          if (this.chartDisposed || renderSeq !== this.chartRenderSeq || mode !== this.analysisTab) return
          const refKeys = mode === 'fleet' ? ['fleetBarChartEl'] : ['mainChartEl', 'errorChartEl']
          const requiredEls = refKeys.map(refKey => this.$refs[refKey]).filter(Boolean)
          requiredEls.forEach(el => this.observeChartElement(el))
          const ready = requiredEls.length > 0 && requiredEls.every(el => this.isChartElementReady(el))

          if (!ready && attempts < 12) {
            const timer = window.setTimeout(() => {
              this.chartRenderTimers = this.chartRenderTimers.filter(item => item !== timer)
              if (renderSeq === this.chartRenderSeq && mode === this.analysisTab) this.scheduleChartRender(mode, attempts + 1)
            }, 50)
            this.chartRenderTimers.push(timer)
            return
          }

          if (mode === 'fleet') {
            this.renderFleetBarChart()
          } else {
            this.renderSingleCharts()
          }
        })
      })
    },
    clearScheduledChartRender() {
      if (this.chartRenderRaf) {
        cancelAnimationFrame(this.chartRenderRaf)
        this.chartRenderRaf = null
      }
      ;(this.chartRenderTimers || []).forEach(timer => window.clearTimeout(timer))
      this.chartRenderTimers = []
    },
    setQuickTimeRange(period) {
      const end = new Date()
      const start = new Date(end)
      start.setHours(0, 0, 0, 0)
      end.setHours(23, 59, 59, 999)
      if (period === '3d') start.setDate(end.getDate() - 2)
      if (period === '1w') start.setDate(end.getDate() - 6)
      const fmt = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
      this.timeRange = [`${fmt(start)} 00:00:00`, `${fmt(end)} 23:59:59`]
      this.syncRouteQuery()
      this.fetchComparisonData()
    },
    destroyAllCharts() {
      this.clearScheduledChartRender()
      this.chartRenderSeq += 1
      this.mainChart = null
      this.errorChart = null
      this.fleetBarChart = null
    },
    normalizeTypeName(str) {
      return String(str || '').replace(/[\s_]/g, '').toLowerCase()
    },
    getSeries(apiData, names = []) {
      const entries = Object.entries(apiData || {})
      const targetNorms = names.map(this.normalizeTypeName)
      const exactMatch = entries.find(([k]) => targetNorms.includes(this.normalizeTypeName(k)))
      if (exactMatch) return Array.isArray(exactMatch[1]) ? exactMatch[1] : []
      const match = entries.find(([k]) => {
        const nk = this.normalizeTypeName(k)
        return targetNorms.some(t => nk.includes(t))
      })
      return match && Array.isArray(match[1]) ? match[1] : []
    },
    toFiniteOrNull(value) {
      const n = Number(value)
      return Number.isFinite(n) ? n : null
    },
    toFiniteNumber(value) {
      const n = Number(value)
      return Number.isFinite(n) ? n : null
    },
    hasSeriesValue(data) {
      return Array.isArray(data) && data.some((v) => {
        if (Array.isArray(v)) return v.some(item => Number.isFinite(Number(item)))
        return Number.isFinite(Number(v))
      })
    },
    sanitizeSeriesData(data) {
      return Array.isArray(data) ? data.map(this.toFiniteOrNull) : []
    },
    buildTimeline(...seriesList) {
      const map = new Map()
      seriesList.flat().forEach((item) => {
        const ts = item?.timestamp
        const time = new Date(ts).getTime()
        if (Number.isFinite(time) && !map.has(time)) map.set(time, ts)
      })
      return Array.from(map.entries())
        .sort((a, b) => a[0] - b[0])
        .map(([, timestamp]) => ({ timestamp }))
    },
    formatChartLabel(timestamp) {
      const d = new Date(timestamp)
      if (!Number.isFinite(d.getTime())) return ''
      return `${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
    },
    alignedSeries(baseSeries, targetSeries, valueKey = 'power', toleranceMs = 0) {
      const target = targetSeries || []
      if (!target.length) return (baseSeries || []).map(() => null)
      if (toleranceMs > 0) {
        const sorted = target.map(v => ({ ts: new Date(v.timestamp).getTime(), val: this.toFiniteOrNull(v[valueKey]) })).filter(v => Number.isFinite(v.ts) && Number.isFinite(v.val)).sort((a, b) => a.ts - b.ts)
        return (baseSeries || []).map(v => {
          const t = new Date(v.timestamp).getTime()
          if (!Number.isFinite(t)) return null
          let best = null, bestDist = Infinity
          for (const item of sorted) {
            const dist = Math.abs(item.ts - t)
            if (dist < bestDist) { bestDist = dist; best = item }
            if (item.ts > t + toleranceMs) break
          }
          return (best && bestDist <= toleranceMs) ? best.val : null
        })
      }
      const map = new Map(target.map(v => {
        const t = new Date(v.timestamp)
        return Number.isFinite(t.getTime()) ? [t.toISOString(), this.toFiniteOrNull(v[valueKey])] : null
      }).filter(Boolean))
      return (baseSeries || []).map(v => {
        const t = new Date(v.timestamp)
        if (!Number.isFinite(t.getTime())) return null
        const key = t.toISOString()
        const val = map.get(key)
        return Number.isFinite(val) ? val : null
      })
    },
    calcMetrics(actual, predicted) {
      const pairs = []
      actual.forEach((a, i) => {
        const p = predicted[i]
        if (Number.isFinite(a) && Number.isFinite(p)) pairs.push([a, p])
      })
      if (!pairs.length) return { mae: null, rmse: null, mse: null, acc: null, k: null, unqualifiedPoints: 0, pe: 0 }
      const threshold = 0.2 * this.installedCapacity
      const absErrors = pairs.map(([a, p]) => Math.abs(p - a))
      const sqErrors = pairs.map(([a, p]) => (p - a) ** 2)
      const mse = sqErrors.reduce((s, v) => s + v, 0) / pairs.length
      const rmse = Math.sqrt(mse)
      const mae = absErrors.reduce((s, v) => s + v, 0) / pairs.length
      const acc = 1 - rmse / this.installedCapacity
      const kArr = pairs.map(([a, p]) => ((p - a) / Math.max(Math.abs(a), threshold)) ** 2)
      const k = 1 - Math.sqrt(kArr.reduce((s, v) => s + v, 0) / kArr.length)
      const unqualifiedPoints = pairs.filter(([a, p]) => Math.abs(p - a) > threshold).length
      const pe = acc < 0.83 ? (0.83 - acc) * this.installedCapacity : 0
      return { mae, rmse, mse, acc, k, unqualifiedPoints, pe }
    },
    calcDailyStats(actualSeries, predSeries, qualifiedThreshold) {
      const actualMap = new Map((actualSeries || []).map(v => [new Date(v.timestamp).toISOString(), Number(v.power)]))
      const predMap = new Map((predSeries || []).map(v => [new Date(v.timestamp).toISOString(), Number(v.power)]))
      const dayBucket = {}
      Array.from(predMap.keys()).forEach((ts) => {
        if (!actualMap.has(ts)) return
        const d = ts.slice(0, 10)
        if (!dayBucket[d]) dayBucket[d] = { actual: [], pred: [] }
        const a = actualMap.get(ts)
        const p = predMap.get(ts)
        if (Number.isFinite(a) && Number.isFinite(p)) {
          dayBucket[d].actual.push(a)
          dayBucket[d].pred.push(p)
        }
      })
      const days = Object.values(dayBucket).filter(v => v.actual.length > 0)
      if (!days.length) return { avgAcc: null, qualifiedRate: null }
      const metrics = days.map(d => this.calcMetrics(d.actual, d.pred))
      const accs = metrics.map(m => m.acc).filter(Number.isFinite)
      const avgAcc = accs.length ? (accs.reduce((s, v) => s + v, 0) / accs.length) * 100 : null
      const qualified = metrics.filter(m => Number.isFinite(m.k) && m.k > qualifiedThreshold).length
      return { avgAcc, qualifiedRate: (qualified / metrics.length) * 100 }
    },
    async fetchComparisonData() {
      if (!this.timeRange || this.timeRange.length !== 2) {
        this.$message.warning('请先选择完整时间范围')
        return
      }
      this.syncRouteQuery()
      this.loading = true
      const requestSeq = ++this.fetchSeq
      const requestMode = this.analysisTab
      try {
        if (requestMode === 'single') {
          await this.fetchSingleStationData(requestSeq)
        } else {
          await this.fetchFleetCompareData(requestSeq)
        }
      } catch (error) {
        console.warn('查询功率对比数据失败:', error?.message || error)
      } finally {
        if (requestSeq === this.fetchSeq) this.loading = false
      }
    },
    isStaleRequest(requestSeq, mode) {
      return requestSeq !== this.fetchSeq || this.analysisTab !== mode
    },
    async fetchSingleStationData(requestSeq = this.fetchSeq) {
      this.fleetCompareRows = []
      const rawCode = this.singleFarmCode || farmService.getCurrentFarm()
      const farmCode = this.fleetCompareFarms.some(f => f.code === rawCode) ? rawCode : (this.fleetCompareFarms[0]?.code || '')
      if (!farmCode) {
        this.$message.warning('请先选择场站')
        return
      }
      farmService.setCurrentFarm(farmCode)
      this.updateInstalledCapacity(farmCode)
      const requestTypes = [...this.selectedTypes]
      ;['实测值', '超短期预测', '短期预测', '中期预测', '短期风速预测', '中期风速预测'].forEach((type) => {
        if (!requestTypes.includes(type)) requestTypes.push(type)
      })
      if (!requestTypes.includes('可用容量')) requestTypes.push('可用容量')
      const payload = { start: this.timeRange[0], end: this.timeRange[1], types: requestTypes, farm_code: farmCode, supershort_horizon: 'average' }
      const response = await getPowerCompareData(payload)
      if (this.isStaleRequest(requestSeq, 'single')) return
      const apiData = response?.data?.data || response?.data || {}
      this.chartData = apiData

      const actual = this.getSeries(apiData, ['实测值', 'actual'])
      const supershort = this.getSeries(apiData, ['超短期预测', 'supershort'])
      const short = this.getSeries(apiData, ['短期预测', 'short'])
      const mid = this.getSeries(apiData, ['中期预测', 'mid'])
      const shortWind = this.getSeries(apiData, ['短期风速预测', '短期风速', 'shortwindspeed'])
      const midWind = this.getSeries(apiData, ['中期风速预测', '中期风速', 'midwindspeed'])
      const capacitySeries = this.getSeries(apiData, ['可用容量', 'availablecapacity'])
      const curtailmentSeries = this.getSeries(apiData, ['限电', 'curtail'])
      const windDirectionSeries = this.getSeries(apiData, ['风向', 'winddirection'])

      // 提取预测区间数据
      const shortLowerSeries = this.getSeries(apiData, ['短期预测下限', 'short_lower'])
      const shortUpperSeries = this.getSeries(apiData, ['短期预测上限', 'short_upper'])
      const midLowerSeries = this.getSeries(apiData, ['中期预测下限', 'mid_lower'])
      const midUpperSeries = this.getSeries(apiData, ['中期预测上限', 'mid_upper'])
      const supershortLowerSeries = this.getSeries(apiData, ['超短期预测下限', 'supershort_lower'])
      const supershortUpperSeries = this.getSeries(apiData, ['超短期预测上限', 'supershort_upper'])

      const sortedActual = [...actual]
        .filter(v => Number.isFinite(new Date(v.timestamp).getTime()))
        .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
      const sortedTimeline = this.buildTimeline(
        sortedActual,
        supershort,
        short,
        mid,
        shortWind,
        midWind,
        capacitySeries,
        curtailmentSeries,
        windDirectionSeries
      )
      const labels = sortedTimeline.map(v => this.formatChartLabel(v.timestamp))
      const alignToleranceMs = 10 * 60 * 1000
      const actualValues = this.alignedSeries(sortedTimeline, sortedActual, 'power', alignToleranceMs)
      const superValues = this.alignedSeries(sortedTimeline, supershort, 'power', alignToleranceMs)
      const shortValues = this.alignedSeries(sortedTimeline, short, 'power', alignToleranceMs)
      const midValues = this.alignedSeries(sortedTimeline, mid, 'power', alignToleranceMs)
      const shortWindValues = this.alignedSeries(sortedTimeline, shortWind, 'wind_speed', alignToleranceMs)
      const midWindValues = this.alignedSeries(sortedTimeline, midWind, 'wind_speed', alignToleranceMs)
      const windDirectionValues = this.alignedSeries(sortedTimeline, windDirectionSeries, 'wind_direction', alignToleranceMs)
      const capacityValuesRaw = this.alignedSeries(sortedTimeline, capacitySeries, 'available_capacity', alignToleranceMs)

      const finiteCaps = capacityValuesRaw.filter(Number.isFinite)
      if (finiteCaps.length) {
        const maxCap = Math.max(...finiteCaps)
        if (maxCap > 0) this.installedCapacity = Number((maxCap * 1.05).toFixed(2))
      }

      const capacityValues = capacityValuesRaw.some(Number.isFinite) ? capacityValuesRaw : labels.map(() => this.installedCapacity)
      const curtailmentValues = this.alignedSeries(sortedTimeline, curtailmentSeries, 'value', alignToleranceMs)

      // 对齐预测区间数据
      const shortLowerValues = this.alignedSeries(sortedTimeline, shortLowerSeries, 'power', alignToleranceMs)
      const shortUpperValues = this.alignedSeries(sortedTimeline, shortUpperSeries, 'power', alignToleranceMs)
      const midLowerValues = this.alignedSeries(sortedTimeline, midLowerSeries, 'power', alignToleranceMs)
      const midUpperValues = this.alignedSeries(sortedTimeline, midUpperSeries, 'power', alignToleranceMs)
      const supershortLowerValues = this.alignedSeries(sortedTimeline, supershortLowerSeries, 'power', alignToleranceMs)
      const supershortUpperValues = this.alignedSeries(sortedTimeline, supershortUpperSeries, 'power', alignToleranceMs)

      const shortDaily = this.calcDailyStats(sortedActual, short, 0.6)
      const superDaily = this.calcDailyStats(sortedActual, supershort, 0.65)
      const shortMetrics = this.calcMetrics(actualValues, shortValues)
      const superMetrics = this.calcMetrics(actualValues, superValues)
      this.singleMetricsSummary = {
        shortAcc: shortDaily.avgAcc,
        shortQualifiedRate: shortDaily.qualifiedRate,
        supershortAcc: superDaily.avgAcc,
        supershortQualifiedRate: superDaily.qualifiedRate,
        rmse: this.mean([shortMetrics.rmse, superMetrics.rmse]),
        mae: this.mean([shortMetrics.mae, superMetrics.mae]),
        unqualifiedPoints: (shortMetrics.unqualifiedPoints || 0) + (superMetrics.unqualifiedPoints || 0),
        assessmentEnergy: (shortMetrics.pe || 0) + (superMetrics.pe || 0)
      }
      this.exportData.metrics = this.singleMetricsSummary

      this.singleSeriesState = {
        labels,
        actualValues,
        superValues,
        shortValues,
        midValues,
        shortWindValues,
        midWindValues,
        windDirectionValues,
        capacityValues,
        curtailmentValues,
        sortedActual,
        sortedTimeline,
        shortLowerValues,
        shortUpperValues,
        midLowerValues,
        midUpperValues,
        supershortLowerValues,
        supershortUpperValues
      }
      this.exportData.comparison = {
        labels,
        datasets: {
          '实测值': actualValues,
          '超短期预测': superValues,
          '短期预测': shortValues,
          '中期预测': midValues,
          '短期风速预测': shortWindValues,
          '中期风速预测': midWindValues,
          '风向(°)': windDirectionValues,
          '可用容量': capacityValues
        }
      }

      this.scheduleChartRender('single')
      this.$nextTick(() => window.setTimeout(() => this.renderSingleCharts(), 120))
    },
    buildCurtailmentMarkAreas(labels, curtailmentValues) {
      if (!this.showCurtailmentTag || !Array.isArray(curtailmentValues) || !curtailmentValues.length) return []
      const areas = []
      let startIndex = null
      curtailmentValues.forEach((v, i) => {
        const isOn = Number(v) > 0
        if (isOn && startIndex === null) startIndex = i
        if (!isOn && startIndex !== null) {
          areas.push([{ xAxis: labels[startIndex] }, { xAxis: labels[i - 1] }])
          startIndex = null
        }
      })
      if (startIndex !== null && labels.length) {
        areas.push([{ xAxis: labels[startIndex] }, { xAxis: labels[labels.length - 1] }])
      }
      return areas
    },
    buildPointData(data) {
      return this.sanitizeSeriesData(data)
        .map((value, index) => (Number.isFinite(value) ? [index, value] : null))
        .filter(Boolean)
    },
    buildSegmentData(data) {
      const cleanData = this.sanitizeSeriesData(data)
      const segments = []
      let previous = null
      cleanData.forEach((value, index) => {
        if (!Number.isFinite(value)) {
          previous = null
          return
        }
        if (previous) segments.push([previous[0], previous[1], index, value])
        previous = [index, value]
      })
      return segments
    },
    pushCustomCurve(series, name, data, color, yAxisIndex, lineType = 'solid') {
      const points = this.buildPointData(data)
      if (!points.length) return
      series.push({
        name,
        type: 'line',
        yAxisIndex,
        coordinateSystem: 'cartesian2d',
        data: this.sanitizeSeriesData(data),
        connectNulls: false,
        showSymbol: true,
        symbolSize: yAxisIndex === YAXIS_WINDSPEED ? 5 : 4,
        lineStyle: {
          color,
          width: yAxisIndex === YAXIS_WINDSPEED ? 1.6 : 1.8,
          type: lineType
        },
        itemStyle: { color },
        emphasis: { focus: 'series' },
        z: 3
      })
    },
    getMainSeriesFromState() {
      const s = this.singleSeriesState
      if (!s) return []
      const series = []
      const pushPower = (name, data, color) => {
        this.pushCustomCurve(series, name, data, color, YAXIS_POWER)
      }
      const pushWind = (name, data, color) => {
        this.pushCustomCurve(series, name, data, color, YAXIS_WINDSPEED, 'dashed')
      }

      if (this.selectedTypes.includes('实测值')) pushPower('实测值', s.actualValues, '#fb7185')
      if (this.selectedTypes.includes('超短期预测')) pushPower('超短期预测', s.superValues, '#22d3ee')
      if (this.selectedTypes.includes('短期预测')) pushPower('短期预测', s.shortValues, '#60a5fa')
      if (this.selectedTypes.includes('中期预测')) pushPower('中期预测', s.midValues, '#4ade80')
      if (this.selectedTypes.includes('短期风速预测')) pushWind('短期风速预测', s.shortWindValues, '#fbbf24')
      if (this.selectedTypes.includes('中期风速预测')) pushWind('中期风速预测', s.midWindValues, '#c084fc')
      // 可用容量仅用于 installedCapacity 计算，不在图表中显示

      const markAreas = this.buildCurtailmentMarkAreas(s.labels, s.curtailmentValues)
      if (markAreas.length && series.length) {
        series[0].markArea = {
          silent: true,
          itemStyle: { color: 'rgba(255, 99, 71, 0.12)' },
          data: markAreas,
          label: { show: true, color: '#ffd7cc', formatter: '限电时段' }
        }
      }
      return series
    },
    prepareCanvas(refKey) {
      const canvas = this.$refs[refKey]
      if (!canvas) return null
      const parent = canvas.parentElement
      const rect = parent?.getBoundingClientRect()
      const width = Math.max(320, Math.floor(rect?.width || canvas.clientWidth || 800))
      const height = Math.max(220, Math.floor(rect?.height || canvas.clientHeight || 360))
      const ratio = window.devicePixelRatio || 1
      canvas.width = Math.floor(width * ratio)
      canvas.height = Math.floor(height * ratio)
      canvas.style.width = `${width}px`
      canvas.style.height = `${height}px`
      const ctx = canvas.getContext('2d')
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
      ctx.clearRect(0, 0, width, height)
      ctx.font = '12px Consolas, Menlo, monospace'
      ctx.lineCap = 'round'
      ctx.lineJoin = 'round'
      return { canvas, ctx, width, height }
    },
    finiteValues(values) {
      return (values || []).map(Number).filter(Number.isFinite)
    },
    getRange(values, fallbackMin = 0, fallbackMax = 1) {
      const arr = this.finiteValues(values)
      if (!arr.length) return { min: fallbackMin, max: fallbackMax }
      let min = Math.min(...arr)
      let max = Math.max(...arr)
      if (min === max) {
        const pad = Math.max(1, Math.abs(max) * 0.1)
        min -= pad
        max += pad
      }
      const pad = (max - min) * 0.08
      return { min: min - pad, max: max + pad }
    },
    getPositiveRange(values, fallbackMax = 1) {
      const range = this.getRange(values, 0, fallbackMax)
      return { min: 0, max: Math.max(fallbackMax, range.max) }
    },
    drawAxes(ctx, plot, labels, leftRange, rightRange, options = {}) {
      ctx.strokeStyle = 'rgba(159, 182, 204, 0.18)'
      ctx.fillStyle = '#9fb6cc'
      ctx.lineWidth = 1
      for (let i = 0; i <= 4; i += 1) {
        const y = plot.top + (plot.height * i) / 4
        ctx.beginPath()
        ctx.moveTo(plot.left, y)
        ctx.lineTo(plot.right, y)
        ctx.stroke()
        const leftVal = leftRange.max - ((leftRange.max - leftRange.min) * i) / 4
        ctx.fillText(leftVal.toFixed(1), 8, y + 4)
        if (rightRange) {
          const rightVal = rightRange.max - ((rightRange.max - rightRange.min) * i) / 4
          ctx.fillText(rightVal.toFixed(1), plot.right + 10, y + 4)
        }
      }
      ctx.strokeStyle = '#6b8aa3'
      ctx.beginPath()
      ctx.moveTo(plot.left, plot.top)
      ctx.lineTo(plot.left, plot.bottom)
      ctx.lineTo(plot.right, plot.bottom)
      ctx.stroke()
      ctx.fillStyle = '#b8d7eb'
      if (options.leftTitle) ctx.fillText(options.leftTitle, plot.left, 18)
      if (options.rightTitle) ctx.fillText(options.rightTitle, plot.right - 60, 18)
      const labelStep = Math.max(1, Math.ceil(labels.length / 8))
      ctx.fillStyle = '#9fb6cc'
      labels.forEach((label, index) => {
        if (index % labelStep !== 0 && index !== labels.length - 1) return
        const x = plot.left + (plot.width * index) / Math.max(1, labels.length - 1)
        ctx.save()
        ctx.translate(x, plot.bottom + 18)
        ctx.rotate(-Math.PI / 8)
        ctx.fillText(String(label), 0, 0)
        ctx.restore()
      })
    },
    drawLineCanvas(refKey, labels, series, options = {}) {
      const prepared = this.prepareCanvas(refKey)
      if (!prepared) return null
      const { canvas, ctx, width, height } = prepared
      const plot = { left: 58, right: width - 58, top: 32, bottom: height - 46 }
      plot.width = plot.right - plot.left
      plot.height = plot.bottom - plot.top
      const powerSeries = series.filter(item => item.axis !== 'wind')
      const windSeries = series.filter(item => item.axis === 'wind')
      const powerRange = this.getPositiveRange(powerSeries.flatMap(item => item.values), this.installedCapacity)
      const windRange = windSeries.length ? this.getPositiveRange(windSeries.flatMap(item => item.values), 25) : null
      const yOf = (value, range) => plot.bottom - ((value - range.min) / Math.max(1e-9, range.max - range.min)) * plot.height
      const xOf = (index) => plot.left + (plot.width * index) / Math.max(1, labels.length - 1)
      this.drawAxes(ctx, plot, labels, powerRange, windRange, options)
      this.chartMeta[refKey] = { labels, series, plot, type: 'line' }
      if (!series.length) {
        ctx.fillStyle = '#9fb6cc'
        ctx.font = '14px Microsoft YaHei, Arial, sans-serif'
        ctx.fillText('暂无可绘制曲线', plot.left + 18, plot.top + 34)
        return canvas
      }
      series.forEach((item) => {
        const range = item.axis === 'wind' ? windRange : powerRange
        if (!range) return
        ctx.strokeStyle = item.color
        ctx.fillStyle = item.color
        ctx.lineWidth = item.axis === 'wind' ? 1.6 : 1.9
        ctx.setLineDash(item.dashed ? [6, 4] : [])
        let drawing = false
        ctx.beginPath()
        item.values.forEach((raw, index) => {
          const value = Number(raw)
          if (!Number.isFinite(value)) {
            drawing = false
            return
          }
          const x = xOf(index)
          const y = yOf(value, range)
          if (!drawing) {
            ctx.moveTo(x, y)
            drawing = true
          } else {
            ctx.lineTo(x, y)
          }
        })
        ctx.stroke()
        ctx.setLineDash([])
      })
      return canvas
    },
    drawBarLineCanvas(refKey, labels, series, options = {}) {
      const prepared = this.prepareCanvas(refKey)
      if (!prepared) return null
      const { canvas, ctx, width, height } = prepared
      const values = series.flatMap(item => item.values)
      const range = this.getRange(values, -1, 1)
      range.min = Math.min(range.min, 0)
      range.max = Math.max(range.max, 0)
      const plot = { left: 58, right: width - 26, top: 30, bottom: height - 50 }
      plot.width = plot.right - plot.left
      plot.height = plot.bottom - plot.top
      const yOf = (value) => plot.bottom - ((value - range.min) / Math.max(1e-9, range.max - range.min)) * plot.height
      const xOf = (index) => plot.left + (plot.width * index) / Math.max(1, labels.length - 1)
      this.drawAxes(ctx, plot, labels, range, null, options)
      this.chartMeta[refKey] = { labels, series, plot, type: 'barLine' }
      const zeroY = yOf(0)
      const barWidth = Math.max(2, Math.min(14, plot.width / Math.max(1, labels.length) * 0.5))
      series.forEach((item) => {
        ctx.strokeStyle = item.color
        ctx.fillStyle = item.color
        if (item.type === 'bar') {
          item.values.forEach((raw, index) => {
            const value = Number(raw)
            if (!Number.isFinite(value)) return
            const x = xOf(index) - barWidth / 2
            const y = yOf(value)
            ctx.fillRect(x, Math.min(y, zeroY), barWidth, Math.max(1, Math.abs(zeroY - y)))
          })
        } else {
          ctx.lineWidth = 1.8
          let drawing = false
          ctx.beginPath()
          item.values.forEach((raw, index) => {
            const value = Number(raw)
            if (!Number.isFinite(value)) {
              drawing = false
              return
            }
            const x = xOf(index)
            const y = yOf(value)
            if (!drawing) {
              ctx.moveTo(x, y)
              drawing = true
            } else {
              ctx.lineTo(x, y)
            }
          })
          ctx.stroke()
        }
      })
      return canvas
    },
    drawGroupedBarCanvas(refKey, labels, series) {
      const prepared = this.prepareCanvas(refKey)
      if (!prepared) return null
      const { canvas, ctx, width, height } = prepared
      const range = { min: 0, max: 100 }
      const plot = { left: 58, right: width - 24, top: 42, bottom: height - 72 }
      plot.width = plot.right - plot.left
      plot.height = plot.bottom - plot.top
      const yOf = (value) => plot.bottom - ((value - range.min) / (range.max - range.min)) * plot.height
      this.drawAxes(ctx, plot, labels, range, null, { leftTitle: '准确率(%)' })
      const groupWidth = plot.width / Math.max(1, labels.length)
      const barWidth = Math.max(8, Math.min(28, groupWidth / 4))
      this.chartMeta[refKey] = { labels, series, plot, type: 'groupedBar' }
      series.forEach((item, seriesIndex) => {
        ctx.fillStyle = item.color
        item.values.forEach((raw, index) => {
          const value = Number(raw)
          if (!Number.isFinite(value)) return
          const center = plot.left + groupWidth * index + groupWidth / 2
          const x = center + (seriesIndex - 0.5) * (barWidth + 4)
          const y = yOf(value)
          ctx.fillRect(x, y, barWidth, plot.bottom - y)
        })
        ctx.fillRect(plot.left + seriesIndex * 150, 16, 16, 8)
        ctx.fillStyle = '#d9e9ff'
        ctx.fillText(item.name, plot.left + seriesIndex * 150 + 22, 24)
        ctx.fillStyle = item.color
      })
      return canvas
    },
    handleChartMouseMove(event, chartType) {
      const refMap = {
        main: 'mainChartCanvas',
        error: 'errorChartCanvas',
        fleet: 'fleetBarChartCanvas'
      }
      const refKey = refMap[chartType]
      const meta = this.chartMeta[refKey]
      if (!meta?.labels?.length || !meta.plot) {
        this.hideChartTooltip()
        return
      }
      const canvas = event.currentTarget
      const rect = canvas.getBoundingClientRect()
      const x = event.clientX - rect.left
      const plot = meta.plot
      let index = 0
      if (meta.type === 'groupedBar') {
        const groupWidth = plot.width / Math.max(1, meta.labels.length)
        index = Math.floor((x - plot.left) / Math.max(1, groupWidth))
      } else {
        index = Math.round(((x - plot.left) / Math.max(1, plot.width)) * Math.max(1, meta.labels.length - 1))
      }
      index = Math.max(0, Math.min(meta.labels.length - 1, index))
      const lines = [`时间: ${meta.labels[index] || '--'}`]
      if (meta.type === 'groupedBar') lines[0] = `场站: ${meta.labels[index] || '--'}`
      meta.series.forEach((item) => {
        const value = Number(item.values?.[index])
        if (Number.isFinite(value)) {
          const unit = item.axis === 'wind' ? 'm/s' : (item.name.includes('率') ? '%' : 'MW')
          lines.push(`${item.name}: ${value.toFixed(2)}${unit}`)
        }
      })
      if (lines.length <= 1) {
        lines.push('当前点暂无数据')
      }
      this.chartTooltip = {
        visible: true,
        x: Math.min(window.innerWidth - 240, event.clientX + 14),
        y: Math.min(window.innerHeight - 140, event.clientY + 14),
        lines
      }
    },
    hideChartTooltip() {
      this.chartTooltip = { visible: false, x: 0, y: 0, lines: [] }
    },
    renderSingleCharts() {
      if (this.chartDisposed) return
      this.renderMainChart()
      this.renderErrorChart()
    },
    renderMainChart() {
      if (this.chartDisposed) return
      const comparison = this.exportData.comparison || {}
      const labels = comparison.labels || this.singleSeriesState?.labels || []
      const datasets = comparison.datasets || {}
      const state = this.singleSeriesState || {}
      const series = []
      const add = (name, values, color, axis = 'power', dashed = false) => {
        if (this.selectedTypes.includes(name) && this.hasSeriesValue(values)) {
          series.push({ name, values, color, axis, dashed })
        }
      }
      add('实测值', datasets['实测值'] || state.actualValues, '#fb7185')
      add('超短期预测', datasets['超短期预测'] || state.superValues, '#22d3ee')
      add('短期预测', datasets['短期预测'] || state.shortValues, '#60a5fa')
      add('中期预测', datasets['中期预测'] || state.midValues, '#4ade80')
      add('短期风速预测', datasets['短期风速预测'] || state.shortWindValues, '#fbbf24', 'wind', true)
      add('中期风速预测', datasets['中期风速预测'] || state.midWindValues, '#c084fc', 'wind', true)
      this.mainChart = this.drawLineCanvas('mainChartCanvas', labels, series, {
        leftTitle: '功率(MW)',
        rightTitle: '风速(m/s)'
      })
    },
    renderErrorChart() {
      if (this.chartDisposed) return
      const comparison = this.exportData.comparison || {}
      const labels = comparison.labels || this.singleSeriesState?.labels || []
      const datasets = comparison.datasets || {}
      const state = this.singleSeriesState || {}
      const actualValues = datasets['实测值'] || state.actualValues || []
      const shortValues = datasets['短期预测'] || state.shortValues || []
      const superValues = datasets['超短期预测'] || state.superValues || []
      const shortErr = shortValues.map((v, i) => (Number.isFinite(v) && Number.isFinite(actualValues[i]) ? Number(v) - Number(actualValues[i]) : '-'))
      const superErr = superValues.map((v, i) => (Number.isFinite(v) && Number.isFinite(actualValues[i]) ? Number(v) - Number(actualValues[i]) : '-'))
      const hasValidErr = shortErr.some(v => v !== '-') || superErr.some(v => v !== '-')
      if (!hasValidErr) {
        this.errorChart = this.drawBarLineCanvas('errorChartCanvas', labels, [], { leftTitle: '误差(MW)' })
        return
      }
      this.errorChart = this.drawBarLineCanvas('errorChartCanvas', labels, [
        { name: '短期误差', values: shortErr, color: 'rgba(96, 165, 250, 0.75)', type: 'bar' },
        { name: '超短期误差', values: superErr, color: '#22d3ee', type: 'line' }
      ], { leftTitle: '误差(MW)' })
    },
    async fetchFleetCompareData(requestSeq = this.fetchSeq) {
      this.chartData = null
      this.singleSeriesState = null
      const validFarmCodeSet = new Set(this.fleetCompareFarms.map(item => item.code))
      const farmCodes = Array.isArray(this.fleetCompareFarmCodes)
        ? this.fleetCompareFarmCodes.filter(code => code && validFarmCodeSet.has(code))
        : []
      if (!farmCodes.length) {
        this.$message.warning('请至少选择一个场站')
        return
      }
      const [shortResp, superResp] = await Promise.all([
        getFleetMetrics({ start: this.timeRange[0], end: this.timeRange[1], farm_codes: farmCodes, prediction_type: 'short' }),
        getFleetMetrics({ start: this.timeRange[0], end: this.timeRange[1], farm_codes: farmCodes, prediction_type: 'supershort' })
      ])
      if (this.isStaleRequest(requestSeq, 'fleet')) return
      const shortItems = shortResp?.data?.data?.items || []
      const superItems = superResp?.data?.data?.items || []
      const map = new Map()
      shortItems.forEach((item) => {
        const rmse = this.toFiniteNumber(item.rmse)
        const mae = this.toFiniteNumber(item.mae)
        const points = this.toFiniteNumber(item.points)
        map.set(item.farm_code, {
          farm_code: item.farm_code,
          farm_name: item.farm_name || item.farm_code,
          short_acc: Number.isFinite(rmse) ? Math.max(0, 100 * (1 - rmse / this.installedCapacity)) : null,
          short_qualified_rate: Number.isFinite(rmse) ? (rmse / this.installedCapacity <= 0.2 ? 100 : 0) : null,
          supershort_acc: null,
          supershort_qualified_rate: null,
          rmse_avg: rmse,
          mae_avg: mae,
          unqualified_points: Number.isFinite(points) && Number.isFinite(rmse) && rmse / this.installedCapacity > 0.2 ? points : 0
        })
      })
      superItems.forEach((item) => {
        const cur = map.get(item.farm_code)
        if (!cur) return
        const rmse = this.toFiniteNumber(item.rmse)
        const mae = this.toFiniteNumber(item.mae)
        const points = this.toFiniteNumber(item.points)
        cur.supershort_acc = Number.isFinite(rmse) ? Math.max(0, 100 * (1 - rmse / this.installedCapacity)) : null
        cur.supershort_qualified_rate = Number.isFinite(rmse) ? (rmse / this.installedCapacity <= 0.2 ? 100 : 0) : null
        cur.rmse_avg = this.mean([cur.rmse_avg, rmse])
        cur.mae_avg = this.mean([cur.mae_avg, mae])
        cur.unqualified_points += Number.isFinite(points) && Number.isFinite(rmse) && rmse / this.installedCapacity > 0.2 ? points : 0
      })
      this.fleetCompareRows = Array.from(map.values())
      this.exportData.metrics = this.fleetCompareRows
      this.exportData.comparison = null
      this.scheduleChartRender('fleet')
    },
    renderFleetBarChart() {
      if (this.chartDisposed) return
      if (!this.fleetCompareRows?.length) return
      this.fleetBarChart = this.drawGroupedBarCanvas(
        'fleetBarChartCanvas',
        this.fleetCompareRows.map(v => v.farm_name || v.farm_code),
        [
          { name: '短期准确率(%)', values: this.fleetCompareRows.map(v => v.short_acc), color: 'rgba(96, 165, 250, 0.78)' },
          { name: '超短期准确率(%)', values: this.fleetCompareRows.map(v => v.supershort_acc), color: 'rgba(34, 211, 238, 0.78)' }
        ]
      )
    },
    handleExportCommand(command) {
      if (command === 'raw_csv') this.downloadRawCSV()
      if (command === 'metrics_excel') this.downloadMetricsExcel()
      if (command === 'chart_png') this.downloadChartPNG()
    },
    downloadRawCSV() {
      if (!this.exportData.comparison?.datasets) return this.$message.warning('暂无可导出的原始数据')
      const labels = this.exportData.comparison.labels || []
      const datasets = this.exportData.comparison.datasets
      const keys = Object.keys(datasets)
      const rows = [['时间', ...keys]]
      labels.forEach((ts, i) => rows.push([ts, ...keys.map(k => datasets[k][i] ?? '')]))
      this.downloadBlob(`\uFEFF${rows.map(r => r.join(',')).join('\n')}`, 'text/csv;charset=utf-8;', `功率对比原始数据_${Date.now()}.csv`)
    },
    downloadMetricsExcel() {
      const rows = []
      if (this.analysisTab === 'single') {
        rows.push(['指标', '值'])
        rows.push(['短期准确率(%)', this.formatPct(this.singleMetricsSummary.shortAcc)])
        rows.push(['短期合格率(%)', this.formatPct(this.singleMetricsSummary.shortQualifiedRate)])
        rows.push(['超短期准确率(%)', this.formatPct(this.singleMetricsSummary.supershortAcc)])
        rows.push(['超短期合格率(%)', this.formatPct(this.singleMetricsSummary.supershortQualifiedRate)])
        rows.push(['RMSE', this.formatNum(this.singleMetricsSummary.rmse)])
        rows.push(['MAE', this.formatNum(this.singleMetricsSummary.mae)])
        rows.push(['不合格点数', this.singleMetricsSummary.unqualifiedPoints])
        rows.push(['考核电量(MWh)', this.formatNum(this.singleMetricsSummary.assessmentEnergy)])
      } else {
        rows.push(['场站编码', '场站名称', '短期准确率(%)', '超短期准确率(%)', 'RMSE', 'MAE', '不合格点数'])
        this.fleetCompareRows.forEach((r) => rows.push([r.farm_code, r.farm_name, this.formatPct(r.short_acc), this.formatPct(r.supershort_acc), this.formatNum(r.rmse_avg), this.formatNum(r.mae_avg), r.unqualified_points]))
      }
      const html = `<html><head><meta charset="UTF-8"></head><body><table border="1">${rows.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join('')}</tr>`).join('')}</table></body></html>`
      this.downloadBlob(html, 'application/vnd.ms-excel;charset=utf-8;', `考核指标_${Date.now()}.xls`)
    },
    downloadChartPNG() {
      const chart = this.analysisTab === 'single'
        ? (this.mainChart || this.$refs.mainChartCanvas)
        : (this.fleetBarChart || this.$refs.fleetBarChartCanvas)
      if (!chart) return this.$message.warning('暂无可导出的图表')
      const link = document.createElement('a')
      link.href = chart.toDataURL('image/png')
      link.download = `图表导出_${Date.now()}.png`
      link.click()
    },
    downloadBlob(content, mimeType, fileName) {
      const blob = new Blob([content], { type: mimeType })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = fileName
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
    }
  },
  watch: {
    analysisTab() {
      this.destroyAllCharts()
      this.syncRouteQuery()
      this.fetchComparisonData()
    },
    singleFarmCode(newCode) {
      if (this.analysisTab === 'single' && newCode) {
        farmService.setCurrentFarm(newCode)
        this.updateInstalledCapacity(newCode)
      }
      this.syncRouteQuery()
    },
    fleetCompareFarmCodes() {
      this.syncRouteQuery()
    },
    timeRange() {
      this.syncRouteQuery()
    },
    selectedTypes() {
      if (this.analysisTab === 'single' && this.singleSeriesState) this.scheduleChartRender('single')
    },
    showCurtailmentTag() {
      if (this.analysisTab === 'single' && this.singleSeriesState) this.scheduleChartRender('single')
    }
  }
}
</script>

<style scoped>
.power-compare-container { min-height: auto; padding: 18px 22px 28px; color: var(--text-primary); }
.page-title { margin: 0 0 14px; color: #f2f7ff; font-size: 28px; font-weight: 700; }
.analysis-tabs { margin-bottom: 12px; }
.single-view-tabs { margin: 8px 0 12px; }
.summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 14px; }
.summary-card, .control-card, .chart-card, .empty-data-card { background: rgba(8, 24, 39, 0.75); border: 1px solid rgba(116, 174, 214, 0.25); }
.summary-label { color: #9fc1d8; font-size: 12px; margin-bottom: 4px; }
.summary-value { color: #e8f6ff; font-family: Consolas, Menlo, Monaco, monospace; font-size: 16px; line-height: 1.3; }
.summary-warning { color: #ffb867; }
.control-card { margin-bottom: 14px; }
.group-title { color: #b8d7eb; font-size: 12px; margin: 8px 0; }
.control-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.farm-select { min-width: 280px; }
.time-range-picker { min-width: 360px; }
.query-btn { min-width: 92px; }
.card-header { color: #d8edff; font-weight: 600; }
.single-chart-section { display: block !important; width: 100%; margin-top: 12px; }
.chart-card { margin-bottom: 12px; }
.force-chart-card { display: block !important; min-height: 320px !important; outline: 1px solid rgba(18, 215, 255, 0.45); }
.series-legend { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 8px; }
.legend-toggle { display: inline-flex; align-items: center; gap: 6px; height: 28px; padding: 0 10px; border-radius: 6px; border: 1px solid rgba(159, 182, 204, 0.32); background: rgba(10, 28, 45, 0.82); color: #d9e9ff; font-size: 12px; cursor: pointer; }
.legend-toggle.inactive { opacity: 0.42; }
.legend-swatch { width: 18px; height: 3px; border-radius: 2px; }
.chart-wrapper { height: 48vh; min-height: 390px; position: relative; background: rgba(3, 16, 28, 0.45); border: 1px dashed rgba(34, 211, 238, 0.28); }
.chart-wrapper.small { height: 30vh; min-height: 240px; }
.native-chart-canvas { display: block !important; width: 100% !important; height: 100% !important; min-height: 220px; }
.chart-tooltip { position: fixed; z-index: 3000; min-width: 180px; max-width: 280px; padding: 8px 10px; border-radius: 6px; border: 1px solid rgba(34, 211, 238, 0.45); background: rgba(3, 16, 28, 0.95); color: #d9e9ff; font-size: 12px; line-height: 1.6; pointer-events: none; box-shadow: 0 8px 18px rgba(0, 0, 0, 0.35); }
.empty-data-content { text-align: center; color: #a9c9de; }
@media (max-width: 980px) {
  .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .farm-select, .time-range-picker { min-width: 100%; }
  .chart-wrapper { height: 42vh; }
}
</style>
