import { getPowerCompareData } from '../api/powerCompareApi'
import farmService from '../utils/farmService'
import axiosInstance from '../api/axios'

const BIN_WIDTH = 0.5
const MIN_SAMPLES = 5
const CONFIDENCE_SIGMA = 2
const OUTLIER_SIGMA = 3
const CUT_IN_SPEED = 3
const CUT_OUT_SPEED = 25
const CURTAILMENT_STD_THRESHOLD = 0.05
const MIN_CONSECUTIVE = 5
const ISOLATION_WINDOW = 3

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

export function extractWindPowerPairs(rawData, capacity = 779.0) {
  const points = []
  if (!rawData || !Array.isArray(rawData)) return points

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

function getBinIndex(windSpeed) {
  return Math.floor(windSpeed / BIN_WIDTH)
}

function getBinCenter(binIndex) {
  return (binIndex + 0.5) * BIN_WIDTH
}

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

export function detectAnomalies(points, binStats, capacity = 779.0) {
  const binLookup = new Map()
  for (const stat of binStats) {
    binLookup.set(stat.binIndex, stat)
  }

  const results = points.map((p) => {
    const binIdx = getBinIndex(p.windSpeed)
    const stat = binLookup.get(binIdx)

    if (p.windSpeed < CUT_IN_SPEED || p.windSpeed > CUT_OUT_SPEED) {
      return { ...p, type: 'normal', binStat: stat }
    }
    if (!stat) {
      return { ...p, type: 'unknown', binStat: null }
    }

    const deviation = Math.abs(p.power - stat.mean)
    const sigmaMultiple = stat.std > 0 ? deviation / stat.std : 0

    if (p.power >= stat.lower && p.power <= stat.upper) {
      return { ...p, type: 'normal', binStat: stat }
    }

    return {
      ...p,
      type: 'candidate',
      sigmaMultiple,
      belowLower: p.power < stat.lower,
      aboveUpper: p.power > stat.upper,
      binStat: stat,
    }
  })

  classifyAnomalies(results, capacity)
  return results
}

function classifyAnomalies(results, capacity) {
  for (let i = 0; i < results.length; i++) {
    const r = results[i]
    if (r.type !== 'candidate') continue

    if (r.belowLower) {
      const consecutiveBelow = countConsecutive(results, i, (item) =>
        item.type === 'candidate' && item.belowLower
      )

      if (consecutiveBelow >= MIN_CONSECUTIVE) {
        const variance = computeLocalVariance(results, i, consecutiveBelow)
        const localStd = Math.sqrt(variance)
        const ratedWindSpeed = findRatedWindSpeed(results)
        if (r.windSpeed > ratedWindSpeed && localStd < CURTAILMENT_STD_THRESHOLD * capacity) {
          markConsecutive(results, i, consecutiveBelow, 'curtailment')
        } else {
          markConsecutive(results, i, consecutiveBelow, 'underperformance')
        }
        i += consecutiveBelow - 1
        continue
      }
    }

    if (r.sigmaMultiple > OUTLIER_SIGMA && isIsolated(results, i)) {
      r.type = 'outlier'
      continue
    }
    r.type = 'normal'
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

function isIsolated(results, index) {
  for (let d = 1; d <= ISOLATION_WINDOW; d++) {
    const before = results[index - d]
    const after = results[index + d]
    if (before && before.type === 'candidate') return false
    if (after && after.type === 'candidate') return false
  }
  return true
}

export function computeSummary(results) {
  let total = 0
  let outliers = 0
  let curtailments = 0
  let underperformance = 0

  for (const r of results) {
    if (r.type === 'unknown') continue
    total++
    if (r.type === 'outlier') outliers++
    else if (r.type === 'curtailment') curtailments++
    else if (r.type === 'underperformance') underperformance++
  }

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

const ALERT_COOLDOWN_MS = 30 * 60 * 1000
const lastAlertTime = new Map()

export async function createAnomalyAlert(summary, farmCode) {
  if (!summary.alertTriggered) return false

  const key = `${farmCode}_power_curve`
  const lastTime = lastAlertTime.get(key) || 0
  if (Date.now() - lastTime < ALERT_COOLDOWN_MS) return false

  try {
    await axiosInstance.post('/api/v1/alarms', {
      source: 'power_curve_analysis',
      farm_code: farmCode,
      module: '功率曲线分析',
      level: 'warning',
      message: `功率曲线异常率达 ${(summary.abnormalRate * 100).toFixed(1)}%，超过 15% 阈值。离群点: ${summary.outliers}, 限电: ${summary.curtailments}, 欠发: ${summary.underperformance}`,
      status: 'open',
    })
    lastAlertTime.set(key, Date.now())
    return true
  } catch {
    return false
  }
}
