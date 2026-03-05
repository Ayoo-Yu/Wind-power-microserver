import { getFarms } from '../api/farmApi'
import { getPowerCompareData } from '../api/powerCompareApi'
import { getReportLogs } from '../api/reportApi'
import farmService from '../utils/farmService'

const TASK_KEYS = [
  { key: 'scada', label: 'SCADA接入' },
  { key: 'nwp', label: '气象NWP拉取' },
  { key: 'ultra', label: '超短期计算' },
  { key: 'short', label: '短期计算' },
  { key: 'grid', label: '电网通信' }
]

function nowRange() {
  const now = new Date()
  const start = new Date(now)
  start.setHours(0, 0, 0, 0)
  const end = new Date(now)
  end.setHours(23, 59, 59, 999)

  const fmt = (d) => {
    const y = d.getFullYear()
    const m = `${d.getMonth() + 1}`.padStart(2, '0')
    const day = `${d.getDate()}`.padStart(2, '0')
    const hh = `${d.getHours()}`.padStart(2, '0')
    const mm = `${d.getMinutes()}`.padStart(2, '0')
    const ss = `${d.getSeconds()}`.padStart(2, '0')
    return `${y}-${m}-${day} ${hh}:${mm}:${ss}`
  }

  return { start: fmt(start), end: fmt(end) }
}

function safeNumber(value, fallback = 0) {
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}

function extractApiData(response) {
  if (!response) return {}
  if (response.data?.data && typeof response.data.data === 'object') return response.data.data
  if (response.data && typeof response.data === 'object') return response.data
  return {}
}

function unwrapItems(payload) {
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.items)) return payload.items
  if (Array.isArray(payload?.logs)) return payload.logs
  if (Array.isArray(payload?.data?.items)) return payload.data.items
  if (Array.isArray(payload?.data?.logs)) return payload.data.logs
  if (Array.isArray(payload?.data)) return payload.data
  return []
}

function normalizeSeries(data = []) {
  if (!Array.isArray(data)) return []
  return data
    .map((item) => ({
      timestamp: item?.timestamp || item?.time || item?.ts || item?.datetime,
      power: safeNumber(item?.power ?? item?.value ?? item?.wp_true ?? item?.wp_pred, null)
    }))
    .filter(item => item.timestamp)
}

function pickSeriesByCandidate(data, candidates = []) {
  for (const key of candidates) {
    if (Array.isArray(data?.[key])) return normalizeSeries(data[key])
  }
  const normalizedCandidates = candidates.map(s => s.toLowerCase())
  const matchKey = Object.keys(data || {}).find((key) =>
    normalizedCandidates.some(candidate => key.toLowerCase().includes(candidate))
  )
  if (!matchKey) return []
  return normalizeSeries(data[matchKey])
}

function pickArraySeries(data) {
  return Object.values(data || {})
    .filter(value => Array.isArray(value))
    .map(row => normalizeSeries(row))
    .filter(row => row.length > 0)
}

function extractSeriesFromPowerCompare(data = {}) {
  const actual = pickSeriesByCandidate(data, ['actual', 'real', 'measured', '实测'])
  const shortTerm = pickSeriesByCandidate(data, ['short_term', 'shortterm', 'short', '短期'])
  const ultraShort = pickSeriesByCandidate(data, ['supershort', 'ultra', '超短'])
  const predicted = pickSeriesByCandidate(data, ['predicted', 'forecast', '预测'])
  const availableCap = pickSeriesByCandidate(data, ['available_capacity', 'availablecap', '可用容量'])

  if (actual.length || shortTerm.length || ultraShort.length || predicted.length || availableCap.length) {
    return { actual, shortTerm, ultraShort, predicted, availableCap }
  }

  const series = pickArraySeries(data)
  return {
    actual: series[0] || [],
    shortTerm: series[1] || [],
    ultraShort: series[2] || [],
    predicted: series[1] || [],
    availableCap: []
  }
}

function calcAccuracy(actual = [], predicted = []) {
  const pairCount = Math.min(actual.length, predicted.length)
  if (pairCount === 0) return 0

  let scoreTotal = 0
  let valid = 0
  for (let i = 0; i < pairCount; i += 1) {
    const a = safeNumber(actual[i]?.power, null)
    const p = safeNumber(predicted[i]?.power, null)
    if (a === null || p === null) continue

    const base = Math.max(1, Math.abs(a))
    const err = Math.abs(p - a) / base
    scoreTotal += Math.max(0, 1 - err)
    valid += 1
  }

  return valid > 0 ? (scoreTotal / valid) * 100 : 0
}

function normalizeStatus(status) {
  const text = `${status || ''}`.toLowerCase()
  if (text.includes('error') || text.includes('fail') || text.includes('failed')) return 'error'
  if (text.includes('warn') || text.includes('running') || text.includes('pending')) return 'warn'
  if (text.includes('success') || text.includes('ok')) return 'ok'
  return 'ok'
}

function toHHmm(value) {
  if (!value) return '--:--'
  const date = new Date(value)
  if (!Number.isNaN(date.getTime())) {
    const hh = `${date.getHours()}`.padStart(2, '0')
    const mm = `${date.getMinutes()}`.padStart(2, '0')
    return `${hh}:${mm}`
  }
  const text = String(value)
  const match = text.match(/(\d{2}):(\d{2})/)
  if (match) return `${match[1]}:${match[2]}`
  return text.slice(11, 16) || text.slice(0, 5)
}

function farmCountByScope(activeFarmCode, farms) {
  if (activeFarmCode && activeFarmCode !== 'DEFAULT_FARM') return 1
  return Math.max(1, farms.length)
}

function isUltraType(row) {
  const text = `${row?.report_type || ''}`.toLowerCase()
  return text.includes('supershort') || text.includes('ultra') || text.includes('forecast_short')
}

function isShortType(row) {
  const text = `${row?.report_type || ''}`.toLowerCase()
  return text.includes('forecast_long') || text.includes('short') || text.includes('mid')
}

function isSuccessStatus(status) {
  const text = `${status || ''}`.toLowerCase()
  return text.includes('success') || text.includes('ok')
}

function summarizeReportCompletion(logs, farmTotal) {
  const ultraExpected = farmTotal * 96
  const shortExpected = farmTotal
  const ultraSuccess = logs.filter(row => isUltraType(row) && isSuccessStatus(row.status)).length
  const shortSuccess = logs.filter(row => isShortType(row) && isSuccessStatus(row.status)).length

  return {
    ultra: { success: Math.min(ultraSuccess, ultraExpected), expected: ultraExpected },
    short: { success: Math.min(shortSuccess, shortExpected), expected: shortExpected }
  }
}

function collectFarmLogs(logs, farmCode) {
  return logs.filter((row) => `${row?.farm_code || ''}`.trim() === farmCode)
}

function taskStatusFromLogs(logs, keywords = []) {
  if (!logs.length) return 'warn'
  const related = logs.filter((row) => {
    const text = `${row?.message || ''} ${row?.response_message || ''} ${row?.error_message || ''} ${row?.report_type || ''}`.toLowerCase()
    return keywords.length === 0 || keywords.some(word => text.includes(word))
  })
  if (!related.length) return 'ok'
  const statuses = related.map(row => normalizeStatus(row.status))
  if (statuses.includes('error')) return 'error'
  if (statuses.includes('warn')) return 'warn'
  return 'ok'
}

function buildTaskMatrix(farms = [], logs = [], commMap = new Map()) {
  return farms.map((farm) => {
    const farmLogs = collectFarmLogs(logs, farm.code)
    const isCommOnline = commMap.get(farm.code) === 'ok'
    const scadaStatus = isCommOnline ? 'ok' : 'error'
    return {
      code: farm.code,
      name: farm.name,
      tasks: {
        scada: scadaStatus,
        nwp: taskStatusFromLogs(farmLogs, ['weather', 'nwp', '气象']),
        ultra: taskStatusFromLogs(farmLogs, ['supershort', 'ultra', 'forecast_short', '超短']),
        short: taskStatusFromLogs(farmLogs, ['forecast_long', 'short', 'mid', '短期']),
        grid: taskStatusFromLogs(farmLogs, ['report', 'upload', '上报', '电网'])
      }
    }
  })
}

function weightedAccuracy(values) {
  if (!values.length) return 0
  const valid = values.filter(item => Number.isFinite(item.acc) && item.acc > 0 && item.weight > 0)
  if (!valid.length) return 0
  const totalWeight = valid.reduce((sum, item) => sum + item.weight, 0)
  if (totalWeight <= 0) return 0
  return valid.reduce((sum, item) => sum + item.acc * item.weight, 0) / totalWeight
}

function buildFallbackFarms() {
  return Array.from({ length: 10 }).map((_, idx) => ({
    code: `F${String(idx + 1).padStart(2, '0')}`,
    name: `场站${idx + 1}`,
    capacity: 200
  }))
}

export async function getDashboardOverview({ farmCode } = {}) {
  const activeFarmCode = farmCode || farmService.getCurrentFarm()
  const { start, end } = nowRange()

  let farms = []
  let farmMeta = []
  let logs = []

  try {
    const loaded = await farmService.loadAvailableFarms()
    farms = loaded.filter(f => f.code && f.code !== 'DEFAULT_FARM')
  } catch (error) {
    farms = []
  }

  try {
    const rawFarms = await getFarms()
    farmMeta = Array.isArray(rawFarms)
      ? rawFarms.map(row => ({
          code: row.farm_code,
          name: row.farm_name || row.farm_code,
          capacity: safeNumber(row.capacity, 0)
        }))
      : []
  } catch (error) {
    farmMeta = []
  }

  if (!farms.length) {
    farms = farmMeta.length ? farmMeta : buildFallbackFarms()
  } else {
    const metaMap = new Map(farmMeta.map(item => [item.code, item]))
    farms = farms.map((farm) => ({
      code: farm.code,
      name: farm.name,
      capacity: safeNumber(metaMap.get(farm.code)?.capacity, 200)
    }))
  }

  const selectedFarms = activeFarmCode && activeFarmCode !== 'DEFAULT_FARM'
    ? farms.filter(f => f.code === activeFarmCode)
    : farms

  try {
    const logsResp = await getReportLogs({
      farm_code: activeFarmCode,
      start_time: start,
      end_time: end,
      page: 1,
      page_size: 500,
      per_page: 500
    })
    logs = unwrapItems(logsResp?.data)
  } catch (error) {
    logs = []
  }

  const compareList = await Promise.all(
    selectedFarms.map(async (farm) => {
      try {
        const compareResp = await getPowerCompareData({ start, end, farm_code: farm.code })
        const data = extractApiData(compareResp)
        const series = extractSeriesFromPowerCompare(data)
        const latestActual = series.actual.length ? safeNumber(series.actual[series.actual.length - 1].power, 0) : 0
        const shortSeries = series.shortTerm.length ? series.shortTerm : series.predicted
        const ultraSeries = series.ultraShort
        return {
          code: farm.code,
          latestActual,
          shortAcc: calcAccuracy(series.actual, shortSeries),
          shortWeight: Math.min(series.actual.length, shortSeries.length),
          ultraAcc: calcAccuracy(series.actual, ultraSeries),
          ultraWeight: Math.min(series.actual.length, ultraSeries.length),
          online: series.actual.length > 0 || shortSeries.length > 0 || ultraSeries.length > 0
        }
      } catch (error) {
        return {
          code: farm.code,
          latestActual: 0,
          shortAcc: 0,
          shortWeight: 0,
          ultraAcc: 0,
          ultraWeight: 0,
          online: false
        }
      }
    })
  )

  const commMap = new Map(compareList.map(item => [item.code, item.online ? 'ok' : 'error']))
  const stationTotal = Math.max(1, selectedFarms.length)
  const onlineCount = compareList.filter(item => item.online).length
  const offlineCount = Math.max(0, stationTotal - onlineCount)
  const totalCapacity = selectedFarms.reduce((sum, farm) => sum + safeNumber(farm.capacity, 200), 0)
  const totalPower = compareList.reduce((sum, item) => sum + safeNumber(item.latestActual, 0), 0)
  const loadRate = totalCapacity > 0 ? (totalPower / totalCapacity) * 100 : 0

  const shortAcc = weightedAccuracy(compareList.map(item => ({ acc: item.shortAcc, weight: item.shortWeight })))
  const ultraAcc = weightedAccuracy(compareList.map(item => ({ acc: item.ultraAcc, weight: item.ultraWeight })))
  const completion = summarizeReportCompletion(logs, farmCountByScope(activeFarmCode, selectedFarms))

  return {
    cards: [
      {
        key: 'station_comm',
        type: 'station-comm',
        label: '场站通讯状态',
        value: {
          online: onlineCount,
          total: stationTotal,
          offline: offlineCount
        }
      },
      {
        key: 'power_capacity',
        type: 'power-capacity',
        label: '当前总功率 / 总装机容量',
        value: {
          power: Math.round(totalPower),
          capacity: Math.round(totalCapacity),
          loadRate: Number(loadRate.toFixed(1))
        }
      },
      {
        key: 'accuracy',
        type: 'accuracy-split',
        label: '综合预测准确率',
        value: {
          shortTerm: Number(shortAcc.toFixed(1)),
          ultraShort: Number(ultraAcc.toFixed(1))
        }
      },
      {
        key: 'report_completion',
        type: 'report-completion',
        label: '今日上报完成率',
        value: {
          ultraSuccess: completion.ultra.success,
          ultraExpected: completion.ultra.expected,
          shortSuccess: completion.short.success,
          shortExpected: completion.short.expected
        }
      }
    ],
    topology: buildTaskMatrix(selectedFarms, logs, commMap)
  }
}

function buildFallbackTrend() {
  const now = new Date()
  const start = new Date(now)
  start.setHours(0, 0, 0, 0)
  const points = []
  for (let i = 0; i < 96; i += 1) {
    const ts = new Date(start.getTime() + i * 15 * 60 * 1000)
    const hour = i / 4
    const shortTerm = Number((280 + Math.sin(hour / 2.6) * 90 + hour * 4.3).toFixed(1))
    const ultraShort = Number((shortTerm + Math.sin(hour * 1.1) * 18).toFixed(1))
    const cap = 420
    const isFuture = ts.getTime() > now.getTime()
    points.push({
      time: ts.toISOString(),
      label: toHHmm(ts.toISOString()),
      actual: isFuture ? null : Number((shortTerm + Math.sin(hour * 0.7) * 14).toFixed(1)),
      shortTerm,
      ultraShort: ts.getTime() <= now.getTime() + 4 * 60 * 60 * 1000 ? ultraShort : null,
      availableCap: cap
    })
  }
  return points
}

function mergeTrendSeries(actual, shortTerm, ultraShort, availableCap) {
  const now = Date.now()
  const maxUltraMs = now + 4 * 60 * 60 * 1000
  const tsSet = new Set()
  ;[actual, shortTerm, ultraShort, availableCap].forEach((arr) => {
    arr.forEach(item => tsSet.add(item.timestamp))
  })
  const sorted = [...tsSet]
    .map((ts) => ({ raw: ts, ms: new Date(ts).getTime() }))
    .filter(item => Number.isFinite(item.ms))
    .sort((a, b) => a.ms - b.ms)

  if (!sorted.length) return []

  const toMap = (arr) => new Map(arr.map(item => [item.timestamp, safeNumber(item.power, null)]))
  const actualMap = toMap(actual)
  const shortMap = toMap(shortTerm)
  const ultraMap = toMap(ultraShort)
  const capMap = toMap(availableCap)

  const maxObserved = Math.max(
    ...sorted.map((item) => Math.max(
      safeNumber(actualMap.get(item.raw), 0),
      safeNumber(shortMap.get(item.raw), 0),
      safeNumber(ultraMap.get(item.raw), 0)
    ))
  )
  const fallbackCap = maxObserved > 0 ? Number((maxObserved * 1.15).toFixed(1)) : 100

  return sorted.map((item) => {
    const actualVal = actualMap.has(item.raw) ? actualMap.get(item.raw) : null
    const shortVal = shortMap.has(item.raw) ? shortMap.get(item.raw) : null
    const ultraVal = ultraMap.has(item.raw) ? ultraMap.get(item.raw) : null
    const capVal = capMap.has(item.raw) ? capMap.get(item.raw) : fallbackCap
    const isFuture = item.ms > now
    return {
      time: item.raw,
      label: toHHmm(item.raw),
      actual: isFuture ? null : actualVal,
      shortTerm: shortVal,
      ultraShort: item.ms <= maxUltraMs ? ultraVal : null,
      availableCap: capVal
    }
  })
}

export async function getDashboardTrend({ farmCode, start, end } = {}) {
  const activeFarmCode = farmCode || farmService.getCurrentFarm()
  const range = start && end ? { start, end } : nowRange()

  try {
    const resp = await getPowerCompareData({
      start: range.start,
      end: range.end,
      farm_code: activeFarmCode
    })
    const data = extractApiData(resp)
    const series = extractSeriesFromPowerCompare(data)
    const shortSeries = series.shortTerm.length ? series.shortTerm : series.predicted
    const merged = mergeTrendSeries(series.actual, shortSeries, series.ultraShort, series.availableCap)
    if (merged.length > 0) return merged
  } catch (error) {
    console.warn('getDashboardTrend fallback:', error)
  }

  return buildFallbackTrend()
}

export async function getDashboardStationRank({ farmCode, start, end } = {}) {
  const range = start && end ? { start, end } : nowRange()

  try {
    const farms = await farmService.loadAvailableFarms()
    const codes = farms.map(item => item.code).filter(code => code && code !== 'DEFAULT_FARM')
    const targetCodes = farmCode && farmCode !== 'DEFAULT_FARM' ? [farmCode] : codes

    const ranked = await Promise.all(
      targetCodes.map(async (code) => {
        try {
          const resp = await getPowerCompareData({
            start: range.start,
            end: range.end,
            farm_code: code
          })
          const data = extractApiData(resp)
          const { actual } = extractSeriesFromPowerCompare(data)
          const avg = actual.length
            ? actual.reduce((sum, cur) => sum + safeNumber(cur.power, 0), 0) / actual.length
            : 0
          return { name: farms.find(f => f.code === code)?.name || code, value: Number(avg.toFixed(2)) }
        } catch (error) {
          return { name: farms.find(f => f.code === code)?.name || code, value: 0 }
        }
      })
    )

    const sorted = ranked.sort((a, b) => b.value - a.value).slice(0, 8)
    if (sorted.length > 0) return sorted
  } catch (error) {
    console.warn('getDashboardStationRank fallback:', error)
  }

  return [
    { name: 'Station A', value: 320 },
    { name: 'Station B', value: 280 },
    { name: 'Station C', value: 260 },
    { name: 'Station D', value: 240 }
  ]
}

export async function getDashboardWeatherSnapshot({ farmCode } = {}) {
  const activeFarmCode = farmCode || farmService.getCurrentFarm()
  const farms = farmService.getAvailableFarms().filter(f => f.code !== 'DEFAULT_FARM')

  if (!farms.length) {
    return {
      mode: 'fleet',
      rows: [
        { code: 'avg_wind', label: '全场平均风速', value: 6.8, unit: 'm/s', hint: '较昨日 +0.4 m/s' },
        { code: 'p90_wind', label: 'P90风速', value: 9.2, unit: 'm/s', hint: '高风速场站 2/10' },
        { code: 'gust_warn', label: '恶劣天气预警', value: 1, unit: '条', hint: '大风黄色预警' },
        { code: 'low_wind', label: '低风速场站', value: 2, unit: '座', hint: '建议关注限电策略' }
      ]
    }
  }

  if (activeFarmCode && activeFarmCode !== 'DEFAULT_FARM') {
    const station = farms.find(f => f.code === activeFarmCode) || farms[0]
    return {
      mode: 'station',
      rows: [
        {
          code: station.code,
          name: station.name,
          windSpeed: 6.9,
          windDirection: 'NE',
          pressure: 1008,
          temperature: 16
        },
        {
          code: `${station.code}-future`,
          name: '未来4小时风速',
          windSpeed: 7.5,
          windDirection: 'ENE',
          pressure: 1005,
          temperature: 15
        }
      ]
    }
  }

  const avgWind = farms.reduce((sum, _, idx) => sum + (5.8 + idx * 0.6), 0) / Math.max(1, farms.length)
  return {
    mode: 'fleet',
    rows: [
      { code: 'avg_wind', label: '全场平均风速', value: Number(avgWind.toFixed(1)), unit: 'm/s', hint: '集团视角' },
      { code: 'bad_weather', label: '恶劣天气预警', value: 2, unit: '条', hint: '沿海区域阵风增强' },
      { code: 'nwp_delay', label: 'NWP延迟场站', value: 1, unit: '座', hint: '建议优先排查链路' },
      { code: 'high_load', label: '高负荷场站', value: 3, unit: '座', hint: '负荷率 > 80%' }
    ]
  }
}

function normalizeEventLevel(row) {
  const status = `${row?.status || ''}`.toLowerCase()
  if (status.includes('fail') || status.includes('error')) return 'error'
  if (status.includes('warn') || status.includes('running') || status.includes('pending')) return 'warn'
  return 'info'
}

function levelText(level) {
  if (level === 'error') return 'ERROR'
  if (level === 'warn') return 'WARN'
  return 'INFO'
}

function resolveEventCategory(row) {
  const text = `${row?.report_type || ''} ${row?.message || ''} ${row?.response_message || ''} ${row?.error_message || ''}`.toLowerCase()
  if (
    text.includes('forecast') ||
    text.includes('report') ||
    text.includes('short') ||
    text.includes('supershort') ||
    text.includes('上报') ||
    text.includes('误差')
  ) {
    return 'business'
  }
  return 'system'
}

export async function getDashboardEvents({ farmCode, limit = 10 } = {}) {
  const activeFarmCode = farmCode || farmService.getCurrentFarm()
  const { start, end } = nowRange()

  try {
    const resp = await getReportLogs({
      farm_code: activeFarmCode,
      start_time: start,
      end_time: end,
      page: 1,
      page_size: Math.max(limit * 3, 20),
      per_page: Math.max(limit * 3, 20)
    })

    const rows = unwrapItems(resp?.data)
    const mapped = rows.slice(0, limit * 3).map((row, idx) => {
      const level = normalizeEventLevel(row)
      const farmName = row.farm_code ? `[${row.farm_code}] ` : ''
      const message = row.error_message || row.response_message || row.message || `${row.report_type || 'system'} task updated`
      return {
        id: row.id || row.log_id || `${idx}-${row.report_time || row.created_at || 'evt'}`,
        time: toHHmm(row.report_time || row.created_at || row.timestamp || '--:--'),
        level,
        levelText: levelText(level),
        category: resolveEventCategory(row),
        message: `${farmName}${message}`
      }
    })

    if (mapped.length > 0) return mapped.slice(0, limit)
  } catch (error) {
    console.warn('getDashboardEvents fallback:', error)
  }

  return [
    { id: 'evt-1', time: '14:15', level: 'info', levelText: 'INFO', category: 'system', message: '气象数据拉取成功，耗时 1.2s' },
    { id: 'evt-2', time: '14:10', level: 'warn', levelText: 'WARN', category: 'business', message: '[F02] 超短期预测误差率接近阈值' },
    { id: 'evt-3', time: '14:03', level: 'info', levelText: 'INFO', category: 'business', message: '[F01] 短期预测上报成功' },
    { id: 'evt-4', time: '13:56', level: 'error', levelText: 'ERROR', category: 'business', message: '[F03] 14:15 超短期上报失败' },
    { id: 'evt-5', time: '13:42', level: 'info', levelText: 'INFO', category: 'system', message: '数据库连接恢复正常' }
  ]
}

export { TASK_KEYS }
