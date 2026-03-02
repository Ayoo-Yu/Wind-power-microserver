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

export function getAutoPredictStatus(farmCode) {
  const params = { farm_code: resolveFarmCode(farmCode) }
  return withLegacyFallback(
    () => axiosInstance.get('/api/v1/autopredict/status', { params }),
    () => axiosInstance.get('/api/status', { params })
  )
}

export function controlAutoPredict(action, predictionType, farmCode) {
  const payload = {
    type: predictionType,
    farm_code: resolveFarmCode(farmCode)
  }
  return withLegacyFallback(
    () => axiosInstance.post(`/api/v1/autopredict/${action}`, payload),
    () => axiosInstance.post(`/api/${action}`, payload)
  )
}

export function getAutoPredictLogs(predictionType, farmCode, options = {}) {
  const params = {
    type: predictionType,
    farm_code: resolveFarmCode(farmCode),
    logType: options.logType || 'train',
    date: options.date,
    lines: options.lines || 500
  }
  return withLegacyFallback(
    () => axiosInstance.get('/api/v1/autopredict/logs', { params }),
    () => axiosInstance.get('/api/logs', { params })
  )
}
