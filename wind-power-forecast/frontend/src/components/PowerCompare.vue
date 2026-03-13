
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
        </el-checkbox-group>
        <el-switch v-model="showCapacityLine" active-text="显示可用容量线" />
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

    <template v-if="analysisTab === 'single'">
      <el-tabs v-model="singleViewTab" class="single-view-tabs">
        <el-tab-pane label="曲线分析" name="curve" />
        <el-tab-pane label="风机出力特性（散点图）" name="scatter" />
      </el-tabs>

      <template v-if="singleViewTab === 'curve'">
        <el-card class="chart-card" v-if="chartData">
          <template #header><div class="card-header">主曲线（双Y轴）</div></template>
          <div class="chart-wrapper" ref="mainChartEl" />
        </el-card>
        <el-card class="chart-card" v-if="chartData">
          <template #header><div class="card-header">误差曲线（预测值 - 实测值）</div></template>
          <div class="chart-wrapper small" ref="errorChartEl" />
        </el-card>
      </template>

      <template v-else>
        <el-card class="chart-card" v-if="chartData">
          <template #header><div class="card-header">风机出力特性（散点图）</div></template>
          <div class="chart-wrapper" ref="scatterChartEl" />
        </el-card>
      </template>
    </template>

    <template v-else>
      <el-card class="chart-card" v-if="fleetCompareRows.length > 0">
        <template #header><div class="card-header">多站准确率对比（短期 vs 超短期）</div></template>
        <div class="chart-wrapper" ref="fleetBarChartEl" />
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
    </template>

    <div class="empty-data-container" v-if="!loading && showEmptyState">
      <el-card class="empty-data-card"><div class="empty-data-content"><h3>暂无数据</h3><p>请选择时间范围并点击“查询”。</p></div></el-card>
    </div>

    <LoadingIndicator :visible="loading" message="数据加载中..." />
  </div>
</template>

<script>
import * as echarts from 'echarts'
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
      singleViewTab: 'curve',
      timeRange: [],
      loading: false,
      chartData: null,
      fleetCompareFarms: [],
      singleFarmCode: '',
      fleetCompareFarmCodes: [],
      selectedTypes: ['实测值', '超短期预测', '短期预测', '中期预测', '短期风速预测', '中期风速预测'],
      showCapacityLine: true,
      showCurtailmentTag: true,
      installedCapacity: 453.5,
      mainChart: null,
      errorChart: null,
      scatterChart: null,
      fleetBarChart: null,
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
    showEmptyState() {
      return this.analysisTab === 'single' ? !this.chartData : this.fleetCompareRows.length === 0
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
    }
  },
  async mounted() {
    const now = new Date()
    const fmt = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    this.timeRange = [`${fmt(now)} 00:00:00`, `${fmt(now)} 23:59:59`]
    await this.loadFleetCompareFarms()
    this.singleFarmCode = farmService.getCurrentFarm() || this.fleetCompareFarms[0]?.code || ''
    this.fleetCompareFarmCodes = this.fleetCompareFarms.map(v => v.code)
    this.applyRouteQuery()
    farmService.addListener(this.handleFarmChanged)
    this.fetchComparisonData()
    window.addEventListener('resize', this.resizeCharts)
  },
  beforeUnmount() {
    farmService.removeListener(this.handleFarmChanged)
    window.removeEventListener('resize', this.resizeCharts)
    this.destroyAllCharts()
  },
  methods: {
    handleFarmChanged(code) {
      if (this.analysisTab === 'single') {
        this.singleFarmCode = code
        this.fetchComparisonData()
      }
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
      if (view === 'curve' || view === 'scatter') this.singleViewTab = view

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
        query.view = this.singleViewTab
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
        .filter(f => f && f.code && f.code !== 'DEFAULT_FARM')
        .map(f => ({ code: f.code, name: f.name || f.code }))
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
    getWindDirectionArrow(deg) {
      const d = Number(deg)
      if (!Number.isFinite(d)) return ''
      const normalized = ((d % 360) + 360) % 360
      const arrows = ['↑', '↗', '→', '↘', '↓', '↙', '←', '↖']
      return arrows[Math.round(normalized / 45) % 8]
    },
    resizeCharts() {
      [this.mainChart, this.errorChart, this.scatterChart, this.fleetBarChart].forEach((chart) => chart && chart.resize())
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
      [this.mainChart, this.errorChart, this.scatterChart, this.fleetBarChart].forEach((chart) => { if (chart) chart.dispose() })
      this.mainChart = null
      this.errorChart = null
      this.scatterChart = null
      this.fleetBarChart = null
    },
    ensureChartInstance(chartKey, refKey) {
      const currentEl = this.$refs[refKey]
      const currentChart = this[chartKey]
      if (!currentEl) return null
      if (currentChart && currentChart.getDom() !== currentEl) {
        currentChart.dispose()
        this[chartKey] = null
      }
      if (!this[chartKey]) {
        this[chartKey] = echarts.init(currentEl)
      }
      return this[chartKey]
    },
    normalizeTypeName(str) {
      return String(str || '').replace(/[\s_]/g, '').toLowerCase()
    },
    getSeries(apiData, names = []) {
      const entries = Object.entries(apiData || {})
      const targetNorms = names.map(this.normalizeTypeName)
      const match = entries.find(([k]) => {
        const nk = this.normalizeTypeName(k)
        return targetNorms.some(t => nk.includes(t))
      })
      return match ? match[1] : []
    },
    alignedSeries(baseSeries, targetSeries, valueKey = 'power') {
      const map = new Map((targetSeries || []).map(v => [new Date(v.timestamp).toISOString(), Number(v[valueKey])]))
      return (baseSeries || []).map(v => {
        const key = new Date(v.timestamp).toISOString()
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
      try {
        if (this.analysisTab === 'single') {
          await this.fetchSingleStationData()
        } else {
          await this.fetchFleetCompareData()
        }
      } finally {
        this.loading = false
      }
    },
    async fetchSingleStationData() {
      const farmCode = this.singleFarmCode || farmService.getCurrentFarm()
      if (!farmCode) {
        this.$message.warning('请先选择场站')
        return
      }
      farmService.setCurrentFarm(farmCode)
      const payload = { start: this.timeRange[0], end: this.timeRange[1], types: this.selectedTypes, farm_code: farmCode, supershort_horizon: 'average' }
      const response = await getPowerCompareData(payload)
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

      const sortedActual = [...actual].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
      const labels = sortedActual.map(v => {
        const d = new Date(v.timestamp)
        return `${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
      })
      const actualValues = sortedActual.map(v => Number(v.power))
      const superValues = this.alignedSeries(sortedActual, supershort)
      const shortValues = this.alignedSeries(sortedActual, short)
      const midValues = this.alignedSeries(sortedActual, mid)
      const shortWindValues = this.alignedSeries(sortedActual, shortWind, 'wind_speed')
      const midWindValues = this.alignedSeries(sortedActual, midWind, 'wind_speed')
      const windDirectionValues = this.alignedSeries(sortedActual, windDirectionSeries, 'wind_direction')
      const capacityValuesRaw = this.alignedSeries(sortedActual, capacitySeries, 'available_capacity')

      const installed = Math.max(this.installedCapacity, ...actualValues.filter(Number.isFinite), ...shortValues.filter(Number.isFinite), ...superValues.filter(Number.isFinite), ...capacityValuesRaw.filter(Number.isFinite), 0)
      this.installedCapacity = installed > 0 ? Number((installed * 1.1).toFixed(2)) : this.installedCapacity

      const capacityValues = capacityValuesRaw.some(Number.isFinite) ? capacityValuesRaw : labels.map(() => this.installedCapacity)
      const curtailmentValues = this.alignedSeries(sortedActual, curtailmentSeries, 'value')

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
        sortedActual
      }
      this.exportData.comparison = {
        labels,
        datasets: {
          '实测值': actualValues,
          '超短期预测': superValues,
          '短期预测': shortValues,
          '中期预测': midValues,
          '短期风速': shortWindValues,
          '中期风速': midWindValues,
          '风向(°)': windDirectionValues,
          '可用容量': capacityValues
        }
      }

      this.$nextTick(() => {
        this.renderSingleCharts()
      })
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
    getMainSeriesFromState() {
      const s = this.singleSeriesState
      if (!s) return []
      const series = []
      const pushPower = (name, data, color) => {
        series.push({ name, type: 'line', data, smooth: false, showSymbol: false, lineStyle: { width: 1.7, color }, itemStyle: { color }, yAxisIndex: YAXIS_POWER, connectNulls: true })
      }
      const pushWind = (name, data, color) => {
        series.push({ name, type: 'line', data, smooth: true, showSymbol: false, lineStyle: { width: 1.4, color, type: 'dashed' }, itemStyle: { color }, yAxisIndex: YAXIS_WINDSPEED, connectNulls: true })
      }

      if (this.selectedTypes.includes('实测值')) pushPower('实测值', s.actualValues, '#fb7185')
      if (this.selectedTypes.includes('超短期预测')) pushPower('超短期预测', s.superValues, '#22d3ee')
      if (this.selectedTypes.includes('短期预测')) pushPower('短期预测', s.shortValues, '#60a5fa')
      if (this.selectedTypes.includes('中期预测')) pushPower('中期预测', s.midValues, '#4ade80')
      if (this.selectedTypes.includes('短期风速预测')) pushWind('短期风速', s.shortWindValues, '#fbbf24')
      if (this.selectedTypes.includes('中期风速预测')) pushWind('中期风速', s.midWindValues, '#c084fc')
      if (this.showCapacityLine) pushPower('可用容量', s.capacityValues, '#f59e0b')

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
    renderSingleCharts() {
      if (!this.singleSeriesState) return
      if (this.singleViewTab === 'curve') {
        this.renderMainChart()
        this.renderErrorChart()
      } else {
        this.renderScatterChart()
      }
    },
    renderMainChart() {
      const state = this.singleSeriesState
      if (!state || !this.$refs.mainChartEl) return
      this.mainChart = this.ensureChartInstance('mainChart', 'mainChartEl')
      if (!this.mainChart) return
      const series = this.getMainSeriesFromState()

      this.mainChart.setOption({
        backgroundColor: 'transparent',
        grid: { left: 54, right: 54, top: 36, bottom: 78 },
        legend: { top: 4, textStyle: { color: '#d9e9ff' } },
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'cross' },
          formatter: (params) => {
            const idx = params?.[0]?.dataIndex ?? 0
            const actual = state.actualValues[idx]
            const lines = [`时间: ${state.labels[idx] || '--'}`]
            params.forEach((p) => {
              const unit = p.seriesName.includes('风速') ? 'm/s' : 'MW'
              const val = Number.isFinite(p.data) ? Number(p.data).toFixed(2) : '--'
              lines.push(`${p.marker}${p.seriesName}: ${val}${Number.isFinite(p.data) ? unit : ''}`)
              if (Number.isFinite(actual) && (p.seriesName === '短期预测' || p.seriesName === '超短期预测') && Number.isFinite(p.data)) {
                const dev = ((Number(p.data) - actual) / Math.max(Math.abs(actual), 1e-6)) * 100
                lines.push(`${p.seriesName}瞬时误差率: ${dev >= 0 ? '+' : ''}${dev.toFixed(1)}%${Math.abs(dev) > 20 ? ' ⚠️' : ''}`)
              }
            })
            const windDirection = state.windDirectionValues[idx]
            if (Number.isFinite(windDirection)) lines.push(`风向: ${windDirection.toFixed(0)}° ${this.getWindDirectionArrow(windDirection)}`)
            return lines.join('<br/>')
          }
        },
        xAxis: { type: 'category', data: state.labels, axisLabel: { color: '#9fb6cc' }, axisLine: { lineStyle: { color: '#6b8aa3' } } },
        yAxis: [
          { type: 'value', name: '功率(MW)', axisLabel: { color: '#9fb6cc' }, nameTextStyle: { color: '#9fb6cc' }, splitLine: { lineStyle: { color: 'rgba(159, 182, 204, 0.12)' } } },
          { type: 'value', name: '风速(m/s)', axisLabel: { color: '#9fb6cc' }, nameTextStyle: { color: '#9fb6cc' }, splitLine: { show: false } }
        ],
        dataZoom: [
          { type: 'inside', xAxisIndex: [0], filterMode: 'none' },
          { type: 'slider', xAxisIndex: [0], bottom: 22, height: 18, borderColor: '#37536b', fillerColor: 'rgba(74, 222, 128, 0.2)', textStyle: { color: '#9fb6cc' } }
        ],
        series
      }, true)
    },
    renderErrorChart() {
      const state = this.singleSeriesState
      if (!state || !this.$refs.errorChartEl) return
      this.errorChart = this.ensureChartInstance('errorChart', 'errorChartEl')
      if (!this.errorChart) return
      const toErr = (arr) => arr.map((v, i) => (Number.isFinite(v) && Number.isFinite(state.actualValues[i]) ? Number(v) - Number(state.actualValues[i]) : null))
      const shortErr = toErr(state.shortValues)
      const superErr = toErr(state.superValues)

      this.errorChart.setOption({
        backgroundColor: 'transparent',
        grid: { left: 54, right: 26, top: 30, bottom: 64 },
        legend: { top: 4, textStyle: { color: '#d9e9ff' } },
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: state.labels, axisLabel: { color: '#9fb6cc' }, axisLine: { lineStyle: { color: '#6b8aa3' } } },
        yAxis: { type: 'value', name: '误差(MW)', axisLabel: { color: '#9fb6cc' }, nameTextStyle: { color: '#9fb6cc' }, splitLine: { lineStyle: { color: 'rgba(159, 182, 204, 0.12)' } } },
        dataZoom: [
          { type: 'inside', xAxisIndex: [0], filterMode: 'none' },
          { type: 'slider', xAxisIndex: [0], bottom: 12, height: 18, borderColor: '#37536b', fillerColor: 'rgba(96, 165, 250, 0.2)', textStyle: { color: '#9fb6cc' } }
        ],
        series: [
          { name: '短期误差', type: 'bar', data: shortErr, itemStyle: { color: 'rgba(96, 165, 250, 0.7)' } },
          { name: '超短期误差', type: 'line', data: superErr, smooth: true, showSymbol: false, lineStyle: { color: '#22d3ee', width: 1.6 } },
          { name: '0轴', type: 'line', data: state.labels.map(() => 0), showSymbol: false, lineStyle: { color: '#f1f5f9', type: 'dashed' } }
        ]
      }, true)
    },
    renderScatterChart() {
      const state = this.singleSeriesState
      if (!state || !this.$refs.scatterChartEl) return
      this.scatterChart = this.ensureChartInstance('scatterChart', 'scatterChartEl')
      if (!this.scatterChart) return
      const points = []
      state.sortedActual.forEach((_, i) => {
        const ws = Number.isFinite(state.shortWindValues[i]) ? state.shortWindValues[i] : state.midWindValues[i]
        const power = state.actualValues[i]
        if (Number.isFinite(ws) && Number.isFinite(power)) points.push([ws, power])
      })

      this.scatterChart.setOption({
        backgroundColor: 'transparent',
        grid: { left: 54, right: 24, top: 30, bottom: 42 },
        tooltip: { trigger: 'item', formatter: (p) => `风速: ${Number(p.value[0]).toFixed(2)} m/s<br/>功率: ${Number(p.value[1]).toFixed(2)} MW` },
        xAxis: { type: 'value', name: '实测风速(m/s)', axisLabel: { color: '#9fb6cc' }, nameTextStyle: { color: '#9fb6cc' }, splitLine: { lineStyle: { color: 'rgba(159, 182, 204, 0.12)' } } },
        yAxis: { type: 'value', name: '实测功率(MW)', axisLabel: { color: '#9fb6cc' }, nameTextStyle: { color: '#9fb6cc' }, splitLine: { lineStyle: { color: 'rgba(159, 182, 204, 0.12)' } } },
        series: [{ name: '实测风速-实测功率', type: 'scatter', symbolSize: 6, data: points, itemStyle: { color: 'rgba(45, 212, 191, 0.55)' } }]
      }, true)
    },
    async fetchFleetCompareData() {
      const validFarmCodeSet = new Set(this.fleetCompareFarms.map(item => item.code))
      const farmCodes = Array.isArray(this.fleetCompareFarmCodes)
        ? this.fleetCompareFarmCodes.filter(code => code && code !== 'DEFAULT_FARM' && validFarmCodeSet.has(code))
        : []
      if (!farmCodes.length) {
        this.$message.warning('请至少选择一个场站')
        return
      }
      const [shortResp, superResp] = await Promise.all([
        getFleetMetrics({ start: this.timeRange[0], end: this.timeRange[1], farm_codes: farmCodes, prediction_type: 'short' }),
        getFleetMetrics({ start: this.timeRange[0], end: this.timeRange[1], farm_codes: farmCodes, prediction_type: 'supershort' })
      ])
      const shortItems = shortResp?.data?.data?.items || []
      const superItems = superResp?.data?.data?.items || []
      const map = new Map()
      shortItems.forEach((item) => {
        map.set(item.farm_code, {
          farm_code: item.farm_code,
          farm_name: item.farm_name || item.farm_code,
          short_acc: Number.isFinite(item.rmse) ? Math.max(0, 100 * (1 - item.rmse / this.installedCapacity)) : null,
          short_qualified_rate: Number.isFinite(item.rmse) ? (item.rmse / this.installedCapacity <= 0.2 ? 100 : 0) : null,
          supershort_acc: null,
          supershort_qualified_rate: null,
          rmse_avg: item.rmse,
          mae_avg: item.mae,
          unqualified_points: Number.isFinite(item.points) && Number.isFinite(item.rmse) && item.rmse / this.installedCapacity > 0.2 ? item.points : 0
        })
      })
      superItems.forEach((item) => {
        const cur = map.get(item.farm_code)
        if (!cur) return
        cur.supershort_acc = Number.isFinite(item.rmse) ? Math.max(0, 100 * (1 - item.rmse / this.installedCapacity)) : null
        cur.supershort_qualified_rate = Number.isFinite(item.rmse) ? (item.rmse / this.installedCapacity <= 0.2 ? 100 : 0) : null
        cur.rmse_avg = this.mean([cur.rmse_avg, item.rmse])
        cur.mae_avg = this.mean([cur.mae_avg, item.mae])
        cur.unqualified_points += Number.isFinite(item.points) && Number.isFinite(item.rmse) && item.rmse / this.installedCapacity > 0.2 ? item.points : 0
      })
      this.fleetCompareRows = Array.from(map.values())
      this.exportData.metrics = this.fleetCompareRows
      this.exportData.comparison = null
      this.$nextTick(() => this.renderFleetBarChart())
    },
    renderFleetBarChart() {
      if (!this.$refs.fleetBarChartEl) return
      this.fleetBarChart = this.ensureChartInstance('fleetBarChart', 'fleetBarChartEl')
      if (!this.fleetBarChart) return
      this.fleetBarChart.setOption({
        backgroundColor: 'transparent',
        grid: { left: 54, right: 24, top: 36, bottom: 84 },
        legend: { top: 4, textStyle: { color: '#d9e9ff' } },
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        xAxis: { type: 'category', data: this.fleetCompareRows.map(v => v.farm_name || v.farm_code), axisLabel: { color: '#9fb6cc' } },
        yAxis: { type: 'value', min: 0, max: 100, axisLabel: { color: '#9fb6cc' }, splitLine: { lineStyle: { color: 'rgba(159, 182, 204, 0.12)' } } },
        dataZoom: [
          { type: 'inside', xAxisIndex: [0], filterMode: 'none' },
          { type: 'slider', xAxisIndex: [0], bottom: 18, height: 18, borderColor: '#37536b', fillerColor: 'rgba(45, 212, 191, 0.2)', textStyle: { color: '#9fb6cc' } }
        ],
        series: [
          { name: '短期准确率(%)', type: 'bar', data: this.fleetCompareRows.map(v => v.short_acc), itemStyle: { color: 'rgba(96, 165, 250, 0.75)' } },
          { name: '超短期准确率(%)', type: 'bar', data: this.fleetCompareRows.map(v => v.supershort_acc), itemStyle: { color: 'rgba(34, 211, 238, 0.75)' } }
        ]
      }, true)
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
        ? (this.singleViewTab === 'curve' ? this.mainChart : this.scatterChart)
        : this.fleetBarChart
      if (!chart) return this.$message.warning('暂无可导出的图表')
      const link = document.createElement('a')
      link.href = chart.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#081827' })
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
    singleViewTab() {
      this.syncRouteQuery()
      if (this.singleViewTab === 'curve' && this.scatterChart) {
        this.scatterChart.dispose()
        this.scatterChart = null
      }
      if (this.singleViewTab === 'scatter') {
        if (this.mainChart) {
          this.mainChart.dispose()
          this.mainChart = null
        }
        if (this.errorChart) {
          this.errorChart.dispose()
          this.errorChart = null
        }
      }
      this.$nextTick(() => this.renderSingleCharts())
    },
    singleFarmCode(newCode) {
      if (this.analysisTab === 'single' && newCode) farmService.setCurrentFarm(newCode)
      this.syncRouteQuery()
    },
    fleetCompareFarmCodes() {
      this.syncRouteQuery()
    },
    timeRange() {
      this.syncRouteQuery()
    },
    selectedTypes() {
      if (this.analysisTab === 'single' && this.singleSeriesState) this.$nextTick(() => this.renderSingleCharts())
    },
    showCapacityLine() {
      if (this.analysisTab === 'single' && this.singleSeriesState) this.$nextTick(() => this.renderSingleCharts())
    },
    showCurtailmentTag() {
      if (this.analysisTab === 'single' && this.singleSeriesState) this.$nextTick(() => this.renderSingleCharts())
    }
  }
}
</script>

<style scoped>
.power-compare-container { min-height: 100vh; padding: 18px 22px 28px; color: #fff; }
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
.chart-card { margin-bottom: 12px; }
.chart-wrapper { height: 54vh; }
.chart-wrapper.small { height: 30vh; }
.empty-data-content { text-align: center; color: #a9c9de; }
@media (max-width: 980px) {
  .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .farm-select, .time-range-picker { min-width: 100%; }
  .chart-wrapper { height: 42vh; }
}
</style>
