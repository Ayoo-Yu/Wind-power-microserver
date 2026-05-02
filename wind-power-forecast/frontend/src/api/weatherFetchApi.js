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

export function getWeatherConnections() {
  return withLegacyFallback(
    () => axiosInstance.get('/api/v1/weather-fetch/connections'),
    () => axiosInstance.get('/api/weather-fetch/connections')
  )
}

export function getWeatherTasks() {
  return withLegacyFallback(
    () => axiosInstance.get('/api/v1/weather-fetch/tasks'),
    () => axiosInstance.get('/api/weather-fetch/tasks')
  )
}

export function createWeatherConnection(payload) {
  return withLegacyFallback(
    () => axiosInstance.post('/api/v1/weather-fetch/connections', payload),
    () => axiosInstance.post('/api/weather-fetch/connections', payload)
  )
}

export function updateWeatherConnection(connectionId, payload) {
  const id = encodeURIComponent(String(connectionId))
  return withLegacyFallback(
    () => axiosInstance.put(`/api/v1/weather-fetch/connections/${id}`, payload),
    () => axiosInstance.put(`/api/weather-fetch/connections/${id}`, payload)
  )
}

export function testWeatherConnection(connectionId) {
  const id = encodeURIComponent(String(connectionId))
  return withLegacyFallback(
    () => axiosInstance.post(`/api/v1/weather-fetch/connections/${id}/test`),
    () => axiosInstance.post(`/api/weather-fetch/connections/${id}/test`)
  )
}

export function deleteWeatherConnection(connectionId) {
  const id = encodeURIComponent(String(connectionId))
  return withLegacyFallback(
    () => axiosInstance.delete(`/api/v1/weather-fetch/connections/${id}`),
    () => axiosInstance.delete(`/api/weather-fetch/connections/${id}`)
  )
}

export function runWeatherTask(taskId) {
  const id = encodeURIComponent(String(taskId))
  return withLegacyFallback(
    () => axiosInstance.post(`/api/v1/weather-fetch/tasks/${id}/run`),
    () => axiosInstance.post(`/api/weather-fetch/tasks/${id}/run`)
  )
}

export function createWeatherTask(payload) {
  return withLegacyFallback(
    () => axiosInstance.post('/api/v1/weather-fetch/tasks', payload),
    () => axiosInstance.post('/api/weather-fetch/tasks', payload)
  )
}

export function updateWeatherTask(taskId, payload) {
  const id = encodeURIComponent(String(taskId))
  return withLegacyFallback(
    () => axiosInstance.put(`/api/v1/weather-fetch/tasks/${id}`, payload),
    () => axiosInstance.put(`/api/weather-fetch/tasks/${id}`, payload)
  )
}

export function toggleWeatherTask(taskId) {
  const id = encodeURIComponent(String(taskId))
  return withLegacyFallback(
    () => axiosInstance.post(`/api/v1/weather-fetch/tasks/${id}/toggle`),
    () => axiosInstance.post(`/api/weather-fetch/tasks/${id}/toggle`)
  )
}

export function deleteWeatherTask(taskId) {
  const id = encodeURIComponent(String(taskId))
  return withLegacyFallback(
    () => axiosInstance.delete(`/api/v1/weather-fetch/tasks/${id}`),
    () => axiosInstance.delete(`/api/weather-fetch/tasks/${id}`)
  )
}

export function checkWeatherDirectories(payload) {
  return withLegacyFallback(
    () => axiosInstance.post('/api/v1/weather-fetch/check-directories', payload),
    () => axiosInstance.post('/api/weather-fetch/check-directories', payload)
  )
}

export function getWeatherTaskLogs(taskId, params = {}) {
  const id = encodeURIComponent(String(taskId))
  return withLegacyFallback(
    () => axiosInstance.get(`/api/v1/weather-fetch/tasks/${id}/logs`, { params }),
    () => axiosInstance.get(`/api/weather-fetch/tasks/${id}/logs`, { params })
  )
}

export function getWeatherSchedulerStatus() {
  return withLegacyFallback(
    () => axiosInstance.get('/api/v1/weather-fetch/scheduler/status'),
    () => axiosInstance.get('/api/weather-fetch/scheduler/status')
  )
}

export function restartWeatherScheduler() {
  return withLegacyFallback(
    () => axiosInstance.post('/api/v1/weather-fetch/scheduler/restart'),
    () => axiosInstance.post('/api/weather-fetch/scheduler/restart')
  )
}

export async function uploadManualWeatherFile(formData) {
  const headers = { 'Content-Type': 'multipart/form-data' }
  try {
    return await withLegacyFallback(
      () => axiosInstance.post('/api/v1/weather-fetch/manual-upload', formData, { headers }),
      () => axiosInstance.post('/api/weather-fetch/manual-upload', formData, { headers })
    )
  } catch (error) {
    const file = formData?.get?.('file')
    const isCsv = typeof file?.name === 'string' && file.name.toLowerCase().endsWith('.csv')
    if (!isCsv) {
      throw error
    }

    const fallbackData = new FormData()
    fallbackData.append('file', file)
    fallbackData.append('farm_code', formData.get('farm_code') || '')
    fallbackData.append('table_name', 'weather_data')
    return axiosInstance.post('/operational/api/upload_operational_csv', fallbackData, { headers })
  }
}

// ECMWF 气象数据库状态
export function getEcmwfAvailability(params) {
  return axiosInstance.get('/api/ecmwf/availability', { params })
}

export function getEcmwfLatest(params) {
  return axiosInstance.get('/api/ecmwf/latest', { params })
}

export function getEcmwfData(params) {
  return axiosInstance.get('/api/ecmwf/data', { params, _silent: true })
}
