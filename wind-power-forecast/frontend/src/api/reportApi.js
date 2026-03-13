import axiosInstance from './axios'

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

export function getReportFarms() {
  return withLegacyFallback(
    () => axiosInstance.get('/api/v1/report/farms'),
    () => axiosInstance.get('/api/report/farms')
  )
}

export function getReportConfigs(params = {}) {
  return withLegacyFallback(
    () => axiosInstance.get('/api/v1/report/configs', { params }),
    () => axiosInstance.get('/api/report/configs', { params })
  )
}

export function getReportSchedulerStatus() {
  return withLegacyFallback(
    () => axiosInstance.get('/api/v1/report/scheduler/status'),
    () => axiosInstance.get('/api/report/scheduler/status')
  )
}

export function startReportScheduler() {
  return withLegacyFallback(
    () => axiosInstance.post('/api/v1/report/scheduler/start'),
    () => axiosInstance.post('/api/report/scheduler/start')
  )
}

export function stopReportScheduler() {
  return withLegacyFallback(
    () => axiosInstance.post('/api/v1/report/scheduler/stop'),
    () => axiosInstance.post('/api/report/scheduler/stop')
  )
}

export function getReportLogs(params = {}) {
  return withLegacyFallback(
    () => axiosInstance.get('/api/v1/report/logs', { params }),
    () => axiosInstance.get('/api/report/logs', { params })
  )
}

export function createReportFarm(payload) {
  return withLegacyFallback(
    () => axiosInstance.post('/api/v1/report/farms', payload),
    () => axiosInstance.post('/api/report/farms', payload)
  )
}

export function updateReportFarm(farmId, payload) {
  const safeId = encodeURIComponent(String(farmId))
  return withLegacyFallback(
    () => axiosInstance.put(`/api/v1/report/farms/${safeId}`, payload),
    () => axiosInstance.put(`/api/report/farms/${safeId}`, payload)
  )
}

export function createReportConfig(payload) {
  return withLegacyFallback(
    () => axiosInstance.post('/api/v1/report/configs', payload),
    () => axiosInstance.post('/api/report/configs', payload)
  )
}

export function updateReportConfig(configId, payload) {
  const safeId = encodeURIComponent(String(configId))
  return withLegacyFallback(
    () => axiosInstance.put(`/api/v1/report/configs/${safeId}`, payload),
    () => axiosInstance.put(`/api/report/configs/${safeId}`, payload)
  )
}

export function deleteReportConfig(configId) {
  const safeId = encodeURIComponent(String(configId))
  return withLegacyFallback(
    () => axiosInstance.delete(`/api/v1/report/configs/${safeId}`),
    () => axiosInstance.delete(`/api/report/configs/${safeId}`)
  )
}

export function previewReport(configId) {
  return withLegacyFallback(
    () => axiosInstance.post('/api/v1/report/preview-report', { config_id: configId }),
    () => axiosInstance.post('/api/report/preview-report', { config_id: configId })
  )
}

export function manualReport(payload) {
  return withLegacyFallback(
    () => axiosInstance.post('/api/v1/report/manual-report', payload),
    () => axiosInstance.post('/api/report/manual-report', payload)
  )
}

export function getReportStatistics(params = {}) {
  return withLegacyFallback(
    () => axiosInstance.get('/api/v1/report/statistics', { params }),
    () => axiosInstance.get('/api/report/statistics', { params })
  )
}

export function getQualityMarkers(params = {}) {
  return withLegacyFallback(
    () => axiosInstance.get('/api/v1/report/quality-markers', { params }),
    () => axiosInstance.get('/api/report/quality-markers', { params })
  )
}

export function createQualityMarker(payload) {
  return withLegacyFallback(
    () => axiosInstance.post('/api/v1/report/quality-markers', payload),
    () => axiosInstance.post('/api/report/quality-markers', payload)
  )
}

export function updateQualityMarker(markerId, payload) {
  const safeId = encodeURIComponent(String(markerId))
  return withLegacyFallback(
    () => axiosInstance.put(`/api/v1/report/quality-markers/${safeId}`, payload),
    () => axiosInstance.put(`/api/report/quality-markers/${safeId}`, payload)
  )
}

export function deleteQualityMarker(markerId) {
  const safeId = encodeURIComponent(String(markerId))
  return withLegacyFallback(
    () => axiosInstance.delete(`/api/v1/report/quality-markers/${safeId}`),
    () => axiosInstance.delete(`/api/report/quality-markers/${safeId}`)
  )
}
