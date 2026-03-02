import axiosInstance from './axios'

function resolveFarmCode(farmCode) {
  return farmCode || 'DEFAULT_FARM'
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

function autopredictGet(path, legacyPath, params) {
  return withLegacyFallback(
    () => axiosInstance.get(`/api/v1/autopredict/${path}`, { params }),
    () => axiosInstance.get(`/api/${legacyPath || path}`, { params })
  )
}

function autopredictPost(path, payload = {}, legacyPath) {
  return withLegacyFallback(
    () => axiosInstance.post(`/api/v1/autopredict/${path}`, payload),
    () => axiosInstance.post(`/api/${legacyPath || path}`, payload)
  )
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
  return autopredictPost('schedule', {
    type: predictionType,
    time,
    farm_code: resolveFarmCode(farmCode)
  }, 'schedule')
}

export function deleteAutoPredictTask(predictionType, farmCode) {
  return autopredictPost('delete', {
    type: predictionType,
    farm_code: resolveFarmCode(farmCode)
  }, 'delete')
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
