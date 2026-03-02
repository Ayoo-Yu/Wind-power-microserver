import axiosInstance from './axios'

function resolveFarmCode(farmCode) {
  return farmCode || 'DEFAULT_FARM'
}

export function getAutoPredictStatus(farmCode) {
  return axiosInstance.get('/api/status', {
    params: { farm_code: resolveFarmCode(farmCode) }
  })
}

export function controlAutoPredict(action, predictionType, farmCode) {
  return axiosInstance.post(`/api/${action}`, {
    type: predictionType,
    farm_code: resolveFarmCode(farmCode)
  })
}

export function getAutoPredictLogs(predictionType, farmCode, options = {}) {
  return axiosInstance.get('/api/logs', {
    params: {
      type: predictionType,
      farm_code: resolveFarmCode(farmCode),
      logType: options.logType || 'train',
      date: options.date,
      lines: options.lines || 500
    }
  })
}
