import axiosInstance from './axios'
import farmService from '../utils/farmService'

function resolveFarmCode(farmCode) {
  const directCode = typeof farmCode === 'string' ? farmCode.trim() : ''
  if (directCode) {
    return directCode
  }

  const currentFarm = typeof farmService.getCurrentFarm === 'function'
    ? String(farmService.getCurrentFarm() || '').trim()
    : ''
  if (currentFarm) {
    return currentFarm
  }

  const fallbackFarm = getFallbackFarmCode()
  return fallbackFarm || ''
}

function isInvalidFarmError(error) {
  const status = error?.response?.status
  const message = String(error?.response?.data?.message || error?.response?.data?.error || '')
  return status === 400 && message.includes('无效的场站代码')
}

function getFallbackFarmCode() {
  const farms = farmService.getAvailableFarms()
  if (Array.isArray(farms) && farms.length > 0) {
    const firstRealFarm = farms.find(f => f && typeof f.code === 'string' && f.code.trim())
    if (firstRealFarm) {
      return firstRealFarm.code
    }

    return farms[0]?.code || ''
  }
  return ''
}

function shouldFallbackToLegacy(error) {
  const status = error?.response?.status
  return !error?.response || status === 404 || status === 405
}

async function withLegacyFallback(v1Call, legacyCall) {
  try {
    return await v1Call()
  } catch (error) {
    if (shouldFallbackToLegacy(error)) {
      return legacyCall()
    }
    throw error
  }
}

async function autopredictGet(path, legacyPath, params) {
  try {
    return await withLegacyFallback(
      () => axiosInstance.get(`/api/v1/autopredict/${path}`, { params }),
      () => axiosInstance.get(`/api/${legacyPath || path}`, { params })
    )
  } catch (error) {
    if (!isInvalidFarmError(error)) {
      throw error
    }

    const fallbackFarmCode = getFallbackFarmCode()
    const requestedFarmCode = params?.farm_code
    if (fallbackFarmCode === requestedFarmCode) {
      throw error
    }

    farmService.setCurrentFarm(fallbackFarmCode)
    const fallbackParams = { ...params, farm_code: fallbackFarmCode }

    return withLegacyFallback(
      () => axiosInstance.get(`/api/v1/autopredict/${path}`, { params: fallbackParams }),
      () => axiosInstance.get(`/api/${legacyPath || path}`, { params: fallbackParams })
    )
  }
}

async function autopredictPost(path, payload = {}, legacyPath) {
  try {
    return await withLegacyFallback(
      () => axiosInstance.post(`/api/v1/autopredict/${path}`, payload),
      () => axiosInstance.post(`/api/${legacyPath || path}`, payload)
    )
  } catch (error) {
    if (!isInvalidFarmError(error)) {
      throw error
    }

    const fallbackFarmCode = getFallbackFarmCode()
    const requestedFarmCode = payload?.farm_code
    if (fallbackFarmCode === requestedFarmCode) {
      throw error
    }

    farmService.setCurrentFarm(fallbackFarmCode)
    const fallbackPayload = { ...payload, farm_code: fallbackFarmCode }

    return withLegacyFallback(
      () => axiosInstance.post(`/api/v1/autopredict/${path}`, fallbackPayload),
      () => axiosInstance.post(`/api/${legacyPath || path}`, fallbackPayload)
    )
  }
}

export function getAutoPredictStatus(farmCode) {
  const params = { farm_code: resolveFarmCode(farmCode) }
  return autopredictGet('status', 'status', params)
}

export function controlAutoPredict(action, predictionType, farmCode) {
  const payload = {
    type: predictionType,
    farm_code: resolveFarmCode(farmCode)
  }
  return autopredictPost(action, payload, action)
}

export function controlAutoPredictAll(action, predictionType, farmCodes = []) {
  const normalizedFarmCodes = Array.from(
    new Set(
      (Array.isArray(farmCodes) ? farmCodes : [])
        .map(code => (typeof code === 'string' ? code.trim() : ''))
        .filter(Boolean)
    )
  )

  const payload = {
    action,
    type: predictionType,
    farm_codes: normalizedFarmCodes
  }
  return autopredictPost('control_all', payload, 'control_all')
}

export function controlAutoPredictMatrix(action, predictionTypes = [], farmCodes = []) {
  const normalizedTypes = Array.from(
    new Set(
      (Array.isArray(predictionTypes) ? predictionTypes : [])
        .map(type => (typeof type === 'string' ? type.trim() : ''))
        .filter(Boolean)
    )
  )
  const normalizedFarmCodes = Array.from(
    new Set(
      (Array.isArray(farmCodes) ? farmCodes : [])
        .map(code => (typeof code === 'string' ? code.trim() : ''))
        .filter(Boolean)
    )
  )

  const payload = {
    action,
    types: normalizedTypes,
    farm_codes: normalizedFarmCodes
  }
  return autopredictPost('control_matrix', payload, 'control_matrix')
}

export function getAutoPredictLogs(predictionType, farmCode, options = {}) {
  const params = {
    type: predictionType,
    farm_code: resolveFarmCode(farmCode),
    logType: options.logType || 'train',
    date: options.date,
    lines: options.lines || 500
  }
  return autopredictGet('logs', 'logs', params)
}

export function getAutoPredictHistory(params = {}) {
  return autopredictGet('history', 'history', params)
}

export function getAutoPredictStatusAll() {
  return autopredictGet('status_all', 'status_all', {})
}

export function getAutoPredictOverview() {
  return autopredictGet('overview', 'overview', {})
}

export function getAutoPredictTaskStatus(predictionType, date, farmCode, extraParams = {}) {
  const params = {
    type: predictionType,
    date,
    farm_code: resolveFarmCode(farmCode),
    ...extraParams
  }
  return autopredictGet('task_status', 'task_status', params)
}

export function getAutoPredictScriptInfo(predictionType, farmCode) {
  return autopredictGet('script_info', 'script_info', {
    type: predictionType,
    farm_code: resolveFarmCode(farmCode)
  })
}

export function setAutoPredictSchedule(predictionType, time, farmCode) {
  return autopredictPost(
    'schedule',
    {
      type: predictionType,
      time,
      farm_code: resolveFarmCode(farmCode)
    },
    'schedule'
  )
}

export function deleteAutoPredictTask(predictionType, farmCode) {
  return autopredictPost(
    'delete',
    {
      type: predictionType,
      farm_code: resolveFarmCode(farmCode)
    },
    'delete'
  )
}

export function saveAutoPredictPm2Config() {
  return autopredictPost('save', {}, 'save')
}

export function clearAutoPredictPm2Config() {
  return autopredictPost('clearsave', {}, 'clearsave')
}

export function resurrectAutoPredictPm2Config() {
  return autopredictPost('resurrect', {}, 'resurrect')
}
