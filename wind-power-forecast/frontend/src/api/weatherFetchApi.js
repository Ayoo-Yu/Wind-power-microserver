import axiosInstance from './axios'

import { withLegacyReadFallback } from './legacyFallback.cjs'

export function getWeatherConnections() {
  return withLegacyReadFallback(
    () => axiosInstance.get('/api/v1/weather-fetch/connections'),
    () => axiosInstance.get('/weather-fetch/connections')
  )
}

export function getWeatherTasks() {
  return withLegacyReadFallback(
    () => axiosInstance.get('/api/v1/weather-fetch/tasks'),
    () => axiosInstance.get('/weather-fetch/tasks')
  )
}

export function createWeatherConnection(payload) {
  return axiosInstance.post('/api/v1/weather-fetch/connections', payload)
}

export function updateWeatherConnection(connectionId, payload) {
  const id = encodeURIComponent(String(connectionId))
  return axiosInstance.put(`/api/v1/weather-fetch/connections/${id}`, payload)
}

export function testWeatherConnection(connectionId) {
  const id = encodeURIComponent(String(connectionId))
  return axiosInstance.post(`/api/v1/weather-fetch/connections/${id}/test`)
}

export function deleteWeatherConnection(connectionId) {
  const id = encodeURIComponent(String(connectionId))
  return axiosInstance.delete(`/api/v1/weather-fetch/connections/${id}`)
}

export function runWeatherTask(taskId) {
  const id = encodeURIComponent(String(taskId))
  return axiosInstance.post(`/api/v1/weather-fetch/tasks/${id}/run`)
}

export function createWeatherTask(payload) {
  return axiosInstance.post('/api/v1/weather-fetch/tasks', payload)
}

export function updateWeatherTask(taskId, payload) {
  const id = encodeURIComponent(String(taskId))
  return axiosInstance.put(`/api/v1/weather-fetch/tasks/${id}`, payload)
}

export function toggleWeatherTask(taskId) {
  const id = encodeURIComponent(String(taskId))
  return axiosInstance.post(`/api/v1/weather-fetch/tasks/${id}/toggle`)
}

export function deleteWeatherTask(taskId) {
  const id = encodeURIComponent(String(taskId))
  return axiosInstance.delete(`/api/v1/weather-fetch/tasks/${id}`)
}

export function checkWeatherDirectories(payload) {
  return axiosInstance.post('/api/v1/weather-fetch/check-directories', payload)
}

export function getWeatherTaskLogs(taskId, params = {}) {
  const id = encodeURIComponent(String(taskId))
  return withLegacyReadFallback(
    () => axiosInstance.get(`/api/v1/weather-fetch/tasks/${id}/logs`, { params }),
    () => axiosInstance.get(`/weather-fetch/tasks/${id}/logs`, { params })
  )
}

export function getWeatherSchedulerStatus() {
  return withLegacyReadFallback(
    () => axiosInstance.get('/api/v1/weather-fetch/scheduler/status'),
    () => axiosInstance.get('/weather-fetch/scheduler/status')
  )
}

export function restartWeatherScheduler() {
  return axiosInstance.post('/api/v1/weather-fetch/scheduler/restart')
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

export function getWeatherSnapshot(params) {
  return axiosInstance.get('/api/dashboard/weather_snapshot', { params, _silent: true })
}
