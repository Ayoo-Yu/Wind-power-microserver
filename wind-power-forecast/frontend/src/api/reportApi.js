import axiosInstance from './axios'

import { withLegacyReadFallback } from './legacyFallback.mjs'

export function getReportFarms() {
  return withLegacyReadFallback(
    () => axiosInstance.get('/api/v1/report/farms'),
    () => axiosInstance.get('/api/report/farms')
  )
}

export function getReportConfigs(params = {}) {
  return withLegacyReadFallback(
    () => axiosInstance.get('/api/v1/report/configs', { params }),
    () => axiosInstance.get('/api/report/configs', { params })
  )
}

export function getReportSchedulerStatus() {
  return withLegacyReadFallback(
    () => axiosInstance.get('/api/v1/report/scheduler/status'),
    () => axiosInstance.get('/api/report/scheduler/status')
  )
}

export function startReportScheduler() {
  return axiosInstance.post('/api/v1/report/scheduler/start')
}

export function stopReportScheduler() {
  return axiosInstance.post('/api/v1/report/scheduler/stop')
}

export function getReportOutboxSummary() {
  return axiosInstance.get('/api/v1/report-outbox/summary', { _silent: true })
}

export function getReportOutboxItems(params = {}) {
  return axiosInstance.get('/api/v1/report-outbox/items', { params, _silent: true })
}

export function retryReportOutboxItem(outboxId) {
  const safeId = encodeURIComponent(String(outboxId))
  return axiosInstance.post(`/api/v1/report-outbox/items/${safeId}/retry`)
}

export function getReportLogs(params = {}) {
  return withLegacyReadFallback(
    () => axiosInstance.get('/api/v1/report/logs', { params, _silent: true }),
    () => axiosInstance.get('/api/report/logs', { params, _silent: true })
  )
}

export function createReportFarm(payload) {
  return axiosInstance.post('/api/v1/report/farms', payload)
}

export function updateReportFarm(farmId, payload) {
  const safeId = encodeURIComponent(String(farmId))
  return axiosInstance.put(`/api/v1/report/farms/${safeId}`, payload)
}

export function createReportConfig(payload) {
  return axiosInstance.post('/api/v1/report/configs', payload)
}

export function updateReportConfig(configId, payload) {
  const safeId = encodeURIComponent(String(configId))
  return axiosInstance.put(`/api/v1/report/configs/${safeId}`, payload)
}

export function deleteReportConfig(configId) {
  const safeId = encodeURIComponent(String(configId))
  return axiosInstance.delete(`/api/v1/report/configs/${safeId}`)
}

export function previewReport(configId) {
  return axiosInstance.post('/api/v1/report/preview-report', { config_id: configId })
}

export function manualReport(payload) {
  return axiosInstance.post('/api/v1/report/manual-report', payload)
}

export function getManualInterventionVersions(params = {}) {
  return withLegacyReadFallback(
    () => axiosInstance.get('/api/v1/report/manual-intervention/versions', { params }),
    () => axiosInstance.get('/api/report/manual-intervention/versions', { params })
  )
}

export function createManualInterventionVersion(payload) {
  return axiosInstance.post('/api/v1/report/manual-intervention/versions', payload)
}

export function getManualInterventionVersion(versionId) {
  const safeId = encodeURIComponent(String(versionId))
  return withLegacyReadFallback(
    () => axiosInstance.get(`/api/v1/report/manual-intervention/versions/${safeId}`),
    () => axiosInstance.get(`/api/report/manual-intervention/versions/${safeId}`)
  )
}

export function applyManualInterventionVersion(versionId, payload = {}) {
  const safeId = encodeURIComponent(String(versionId))
  return axiosInstance.post(`/api/v1/report/manual-intervention/versions/${safeId}/apply`, payload)
}

export function getReportStatistics(params = {}) {
  return withLegacyReadFallback(
    () => axiosInstance.get('/api/v1/report/statistics', { params }),
    () => axiosInstance.get('/api/report/statistics', { params })
  )
}

export function getAccuracyStatistics(params = {}) {
  return withLegacyReadFallback(
    () => axiosInstance.get('/api/v1/report/accuracy-statistics', { params }),
    () => axiosInstance.get('/api/report/accuracy-statistics', { params })
  )
}

export function getQualityMarkers(params = {}) {
  return withLegacyReadFallback(
    () => axiosInstance.get('/api/v1/report/quality-markers', { params }),
    () => axiosInstance.get('/api/report/quality-markers', { params })
  )
}

export function createQualityMarker(payload) {
  return axiosInstance.post('/api/v1/report/quality-markers', payload)
}

export function updateQualityMarker(markerId, payload) {
  const safeId = encodeURIComponent(String(markerId))
  return axiosInstance.put(`/api/v1/report/quality-markers/${safeId}`, payload)
}

export function deleteQualityMarker(markerId) {
  const safeId = encodeURIComponent(String(markerId))
  return axiosInstance.delete(`/api/v1/report/quality-markers/${safeId}`)
}
