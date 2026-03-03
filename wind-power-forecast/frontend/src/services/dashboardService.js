import { getFarms } from '../api/farmApi'
import { getPowerCompareData } from '../api/powerCompareApi'
import { getReportLogs } from '../api/reportApi'
import farmService from '../utils/farmService'

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

function normalizeSeries(data = []) {
  if (!Array.isArray(data)) return []
  return data
    .map(item => ({
      timestamp: item?.timestamp || item?.time || item?.ts,
      power: safeNumber(item?.power, null)
    }))
    .filter(item => item.timestamp)
}

function extractApiData(response) {
  if (!response) return {}
  if (response.data?.data && typeof response.data.data === 'object') return response.data.data
  if (response.data && typeof response.data === 'object') return response.data
  return {}
}

function extractSeriesFromPowerCompare(data) {
  const actual = normalizeSeries(data['实测值'] || data.actual || data.real || [])
  const predicted = normalizeSeries(data['短期预测'] || data['超短期预测'] || data.predicted || [])
  return { actual, predicted }
}

function buildFallbackTopology(farms = []) {
  return farms.map((farm, idx) => {
    const angle = (Math.PI * 2 * idx) / Math.max(1, farms.length)
    const radius = 36 + (idx % 2) * 12
    return {
      name: farm.name,
      code: farm.code,
      value: [Math.round(Math.cos(angle) * radius), Math.round(Math.sin(angle) * radius), 60 + (idx % 5) * 8],
      status: idx % 4 === 0 ? 'warn' : 'ok'
    }
  })
}

export async function getDashboardOverview({ farmCode } = {}) {
  const activeFarmCode = farmCode || farmService.getCurrentFarm()
  const { start, end } = nowRange()

  let farms = []
  let alertCount = 0
  let totalPower = 0
  let avgAccuracy = 0

  try {
    farms = await getFarms()
  } catch (error) {
    farms = farmService.getAvailableFarms().map(f => ({ farm_code: f.code, farm_name: f.name }))
  }

  try {
    const logsResp = await getReportLogs({
      farm_code: activeFarmCode,
      status: 'failed',
      start_time: start,
      end_time: end,
      page: 1,
      page_size: 200
    })
    const logs = logsResp?.data?.data?.items || logsResp?.data?.items || logsResp?.data || []
    alertCount = Array.isArray(logs) ? logs.length : 0
  } catch (error) {
    alertCount = 0
  }

  try {
    const compareResp = await getPowerCompareData({
      start,
      end,
      types: ['实测值', '短期预测'],
      farm_code: activeFarmCode,
    })
    const apiData = extractApiData(compareResp)
    const { actual, predicted } = extractSeriesFromPowerCompare(apiData)
    if (actual.length > 0) {
      totalPower = safeNumber(actual[actual.length - 1]?.power, 0)
    }

    const pairCount = Math.min(actual.length, predicted.length)
    if (pairCount > 0) {
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
      avgAccuracy = valid > 0 ? (scoreTotal / valid) * 100 : 0
    }
  } catch (error) {
    totalPower = 0
    avgAccuracy = 0
  }

  return {
    cards: [
      { key: 'farm_total', label: '接入场站总数', value: farms.length, unit: '个' },
      { key: 'accuracy', label: '今日平均准确率', value: avgAccuracy.toFixed(1), unit: '%' },
      { key: 'power', label: '当前总功率', value: Math.round(totalPower), unit: 'MW' },
      { key: 'alerts', label: '今日异常告警数', value: alertCount, unit: '条' }
    ],
    topology: buildFallbackTopology(
      farms.map(item => ({ code: item.farm_code, name: item.farm_name || item.farm_code }))
    )
  }
}

export async function getDashboardTrend({ farmCode, start, end } = {}) {
  const activeFarmCode = farmCode || farmService.getCurrentFarm()
  const range = start && end ? { start, end } : nowRange()
  try {
    const resp = await getPowerCompareData({
      start: range.start,
      end: range.end,
      types: ['实测值', '短期预测'],
      farm_code: activeFarmCode,
    })
    const data = extractApiData(resp)
    const { actual, predicted } = extractSeriesFromPowerCompare(data)
    const points = actual.length > 0 ? actual : predicted
    return points.map((item, idx) => ({
      time: item.timestamp,
      actual: safeNumber(actual[idx]?.power, null),
      predicted: safeNumber(predicted[idx]?.power, null)
    }))
  } catch (error) {
    const fallback = []
    for (let i = 0; i < 24; i += 1) {
      fallback.push({
        time: `${String(i).padStart(2, '0')}:00`,
        actual: 220 + Math.sin(i / 3) * 40 + i,
        predicted: 215 + Math.sin(i / 3 + 0.4) * 35 + i,
      })
    }
    return fallback
  }
}

export async function getDashboardStationRank({ farmCode, start, end } = {}) {
  const range = start && end ? { start, end } : nowRange()
  try {
    const farms = await farmService.loadAvailableFarms()
    const codes = farms.map(item => item.code).filter(code => code && code !== 'DEFAULT_FARM')
    const targetCodes = farmCode && farmCode !== 'DEFAULT_FARM' ? [farmCode] : codes
    const ranked = await Promise.all(targetCodes.map(async (code) => {
      try {
        const resp = await getPowerCompareData({
          start: range.start,
          end: range.end,
          types: ['实测值'],
          farm_code: code
        })
        const data = extractApiData(resp)
        const actual = normalizeSeries(data['实测值'] || data.actual || [])
        const avg = actual.length
          ? actual.reduce((sum, cur) => sum + safeNumber(cur.power, 0), 0) / actual.length
          : 0
        return { name: farms.find(f => f.code === code)?.name || code, value: Number(avg.toFixed(2)) }
      } catch (error) {
        return { name: farms.find(f => f.code === code)?.name || code, value: 0 }
      }
    }))

    const sorted = ranked.sort((a, b) => b.value - a.value).slice(0, 8)
    if (sorted.length > 0) return sorted
  } catch (error) {
    console.warn('getDashboardStationRank fallback:', error)
  }

  return [
    { name: '一场站', value: 320 },
    { name: '二场站', value: 280 },
    { name: '三场站', value: 260 },
    { name: '四场站', value: 240 },
  ]
}
