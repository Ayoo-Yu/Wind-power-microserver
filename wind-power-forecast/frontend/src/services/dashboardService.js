import { getFarms } from '../api/farmApi'
import { getPowerCompareData } from '../api/powerCompareApi'
import { getReportLogs } from '../api/reportApi'
import { getWeatherSnapshot } from '../api/weatherFetchApi'
import farmService from '../utils/farmService'

const TASK_KEYS = [
  { key: 'scada', label: 'SCADA' },
  { key: 'nwp', label: 'NWP' },
  { key: 'ultra', label: '超短期' },
  { key: 'short', label: '短期' },
  { key: 'grid', label: '电网' }
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

function shortFarmName(name) {
  if (!name) return name
  return name.replace(/风电场$/, '')
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
  if (activeFarmCode) return farms.length ? 1 : 0
  return farms.length
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
  if (!logs.length) return 'ok'
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
    const commStatus = commMap.get(farm.code)
    const scadaStatus = commStatus === 'ok' ? 'ok' : commStatus === 'error' ? 'warn' : 'ok'
    return {
      code: farm.code,
      name: shortFarmName(farm.name),
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

export async function getDashboardOverview({ farmCode } = {}) {
  const activeFarmCode = farmCode || farmService.getCurrentFarm()
  const { start, end } = nowRange()

  let farms = []
  let farmMeta = []
  let logs = []

  try {
    const loaded = await farmService.loadAvailableFarms()
    farms = loaded.filter(f => f.code)
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
    farms = farmMeta
  } else {
    const metaMap = new Map(farmMeta.map(item => [item.code, item]))
    farms = farms.map((farm) => ({
      code: farm.code,
      name: farm.name,
      capacity: safeNumber(metaMap.get(farm.code)?.capacity, 0)
    }))
  }

  const selectedFarms = activeFarmCode
    ? farms.filter(f => f.code === activeFarmCode)
    : farms

  try {
    const logsResp = await getReportLogs({
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
        const compareResp = await getPowerCompareData({ start, end, farm_code: farm.code, types: ['实测值', '短期预测', '超短期预测'] })
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

  const shortAcc = weightedAccuracy(compareList.map(item => ({ acc: item.shortAcc, weight: item.shortWeight })))
  const ultraAcc = weightedAccuracy(compareList.map(item => ({ acc: item.ultraAcc, weight: item.ultraWeight })))

  const totalCurrentPower = compareList.reduce((sum, item) => sum + safeNumber(item.latestActual, 0), 0)
  const totalCapacity = selectedFarms.reduce((sum, farm) => sum + safeNumber(farm.capacity, 0), 0)
  const loadRate = totalCapacity > 0 ? (totalCurrentPower / totalCapacity) * 100 : 0

  const onlineFarms = compareList.filter(item => item.online).length
  const totalFarms = compareList.length

  const estimatedDailyEnergy = totalCurrentPower * (new Date().getHours() + new Date().getMinutes() / 60)

  return {
    cards: [
      {
        key: 'accuracy',
        type: 'accuracy-split',
        label: '综合预测准确率',
        theme: 'cyan',
        value: {
          shortTerm: Number(shortAcc.toFixed(2)),
          ultraShort: Number(ultraAcc.toFixed(2))
        }
      },
      {
        key: 'total-power',
        type: 'value-unit',
        label: '当前总功率',
        theme: 'green',
        value: Number(totalCurrentPower.toFixed(1)),
        unit: 'MW',
        sub: [
          { label: '装机容量', value: `${Number(totalCapacity.toFixed(0))} MW` },
          { label: '负荷率', value: `${Number(loadRate.toFixed(1))}%`, highlight: true }
        ]
      },
      {
        key: 'daily-energy',
        type: 'value-unit',
        label: '今日发电量(估)',
        theme: 'yellow',
        value: Number(estimatedDailyEnergy.toFixed(0)),
        unit: 'MWh',
        sub: []
      },
      {
        key: 'farm-online',
        type: 'value-unit',
        label: '场站在线率',
        theme: 'purple',
        value: totalFarms > 0 ? Number(((onlineFarms / totalFarms) * 100).toFixed(1)) : 0,
        unit: '%',
        sub: [
          { label: '在线', value: `${onlineFarms} / ${totalFarms}` }
        ]
      }
    ],
    topology: buildTaskMatrix(farms, logs, commMap)
  }
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

  return sorted.map((item) => {
    const actualVal = actualMap.has(item.raw) ? actualMap.get(item.raw) : null
    const shortVal = shortMap.has(item.raw) ? shortMap.get(item.raw) : null
    const ultraVal = ultraMap.has(item.raw) ? ultraMap.get(item.raw) : null
    const capVal = capMap.has(item.raw) ? capMap.get(item.raw) : null
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

  const isAllFarms = !activeFarmCode

  const fetchSeriesForFarm = async (code) => {
    const resp = await getPowerCompareData({
      start: range.start,
      end: range.end,
      farm_code: code,
      types: ['实测值', '短期预测', '超短期预测']
    })
    return extractSeriesFromPowerCompare(extractApiData(resp))
  }

  const mergeMultiFarmSeries = (allSeries) => {
    const tsMap2 = new Map()
    for (const s of allSeries) {
      for (const pt of s.actual) {
        const key = pt.timestamp
        if (!tsMap2.has(key)) tsMap2.set(key, { timestamp: key, actual: 0, shortTerm: null, ultraShort: null, _ac: 0, _sc: 0, _uc: 0, _sv: 0, _uv: 0 })
        const e = tsMap2.get(key)
        const v = safeNumber(pt.power, null)
        if (v !== null) { e.actual += v; e._ac++ }
      }
      for (const pt of s.shortTerm) {
        const e = tsMap2.get(pt.timestamp)
        if (e) { const v = safeNumber(pt.power, null); if (v !== null) { e.shortTerm = (e.shortTerm || 0) + v; e._sc++; e._sv++ } }
      }
      for (const pt of s.ultraShort) {
        const e = tsMap2.get(pt.timestamp)
        if (e) { const v = safeNumber(pt.power, null); if (v !== null) { e.ultraShort = (e.ultraShort || 0) + v; e._uc++; e._uv++ } }
      }
    }
    const points = [...tsMap2.values()].sort((a, b) => a.timestamp < b.timestamp ? -1 : 1)
    return points.map(p => ({
      timestamp: p.timestamp,
      power: p._ac > 0 ? p.actual : null,
      shortTerm: p._sv > 0 ? p.shortTerm : null,
      ultraShort: p._uv > 0 ? p.ultraShort : null
    }))
  }

  try {
    if (isAllFarms) {
      const farms = await farmService.loadAvailableFarms()
      const codes = farms.map(f => f.code).filter(c => c)
      const allSeries = await Promise.all(codes.map(code => fetchSeriesForFarm(code).catch(() => ({ actual: [], shortTerm: [], ultraShort: [], predicted: [], availableCap: [] }))))
      const aggregated = mergeMultiFarmSeries(allSeries)
      const merged = mergeTrendSeries(
        aggregated.map(p => ({ timestamp: p.timestamp, power: p.power })),
        aggregated.map(p => ({ timestamp: p.timestamp, power: p.shortTerm })),
        aggregated.map(p => ({ timestamp: p.timestamp, power: p.ultraShort })),
        []
      )
      if (merged.length > 0) return merged
    } else {
      const resp = await getPowerCompareData({
        start: range.start,
        end: range.end,
        farm_code: activeFarmCode,
        types: ['实测值', '短期预测', '超短期预测']
      })
      const data = extractApiData(resp)
      const series = extractSeriesFromPowerCompare(data)
      const shortSeries = series.shortTerm.length ? series.shortTerm : series.predicted
      const merged = mergeTrendSeries(series.actual, shortSeries, series.ultraShort, series.availableCap)
      if (merged.length > 0) return merged
    }
  } catch (error) {
    console.warn('getDashboardTrend fallback:', error)
  }
  return []
}

export async function getDashboardStationRank({ farmCode, start, end } = {}) {
  const range = start && end ? { start, end } : nowRange()

  try {
    const farms = await farmService.loadAvailableFarms()
    const codes = farms.map(item => item.code).filter(code => code)
    const targetCodes = farmCode ? [farmCode] : codes

    const ranked = await Promise.all(
      targetCodes.map(async (code) => {
        try {
          const resp = await getPowerCompareData({
            start: range.start,
            end: range.end,
            farm_code: code,
            types: ['实测值']
          })
          const data = extractApiData(resp)
          const { actual } = extractSeriesFromPowerCompare(data)
          const avg = actual.length
            ? actual.reduce((sum, cur) => sum + safeNumber(cur.power, 0), 0) / actual.length
            : 0
          return { name: shortFarmName(farms.find(f => f.code === code)?.name || code), value: Number(avg.toFixed(2)) }
        } catch (error) {
          return { name: shortFarmName(farms.find(f => f.code === code)?.name || code), value: 0 }
        }
      })
    )

    const sorted = ranked.sort((a, b) => b.value - a.value).slice(0, 8)
    if (sorted.length > 0) return sorted
  } catch (error) {
    console.warn('getDashboardStationRank fallback:', error)
  }
  return []
}

export async function getDashboardWeatherSnapshot({ farmCode } = {}) {
  const activeFarmCode = farmCode || farmService.getCurrentFarm()

  try {
    const resp = await getWeatherSnapshot({ farm_code: activeFarmCode })
    const data = resp?.data?.data
    if (data?.metrics?.length) {
      return { mode: 'fleet', metrics: data.metrics, updateTime: data.updateTime }
    }
    return { mode: 'fleet', metrics: [], updateTime: null }
  } catch (error) {
    console.warn('getDashboardWeatherSnapshot backend unavailable:', error)
    return { mode: 'fleet', metrics: [], updateTime: null }
  }
}

function normalizeEventLevel(row) {
  const status = `${row?.status || ''}`.toLowerCase()
  if (status.includes('fail') || status.includes('error')) return 'error'
  if (status.includes('warn') || status.includes('running') || status.includes('pending')) return 'warn'
  return 'info'
}

function levelText(level) {
  if (level === 'error') return '异常'
  if (level === 'warn') return '告警'
  return '正常'
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
  return []
}

export { TASK_KEYS }
