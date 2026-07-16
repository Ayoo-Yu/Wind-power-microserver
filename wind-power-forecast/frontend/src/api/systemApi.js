import axiosInstance from './axios'

import { withLegacyReadFallback } from './legacyFallback.mjs'

export function getSystemHardware() {
  return withLegacyReadFallback(
    () => axiosInstance.get('/api/v1/system/hardware'),
    () => axiosInstance.get('/api/system/hardware')
  )
}

export function getSystemSoftware() {
  return withLegacyReadFallback(
    () => axiosInstance.get('/api/v1/system/software'),
    () => axiosInstance.get('/api/system/software')
  )
}

export function getSystemRuntime() {
  return withLegacyReadFallback(
    () => axiosInstance.get('/api/v1/system/runtime'),
    () => axiosInstance.get('/api/system/runtime')
  )
}

export function getSystemLogs() {
  return withLegacyReadFallback(
    () => axiosInstance.get('/api/v1/system/logs'),
    () => axiosInstance.get('/api/system/logs')
  )
}

export function getAlarms(params = {}) {
  return withLegacyReadFallback(
    () => axiosInstance.get('/api/v1/system/alarms', { params }),
    () => axiosInstance.get('/api/system/alarms', { params })
  )
}

export function getAlarmNotifications() {
  return withLegacyReadFallback(
    () => axiosInstance.get('/api/v1/system/alarms/notifications'),
    () => axiosInstance.get('/api/system/alarms/notifications')
  )
}

export function getAlarmRules() {
  return withLegacyReadFallback(
    () => axiosInstance.get('/api/v1/system/alarm-rules'),
    () => axiosInstance.get('/api/system/alarm-rules')
  )
}

export function createAlarmRule(payload) {
  return axiosInstance.post('/api/v1/system/alarm-rules', payload)
}

export function updateAlarmRule(ruleId, payload) {
  return axiosInstance.put(`/api/v1/system/alarm-rules/${encodeURIComponent(String(ruleId))}`, payload)
}

export function deleteAlarmRule(ruleId) {
  return axiosInstance.delete(`/api/v1/system/alarm-rules/${encodeURIComponent(String(ruleId))}`)
}

export function getAlarmPolicies() {
  return withLegacyReadFallback(
    () => axiosInstance.get('/api/v1/system/alarm-policies'),
    () => axiosInstance.get('/api/system/alarm-policies')
  )
}

export function createAlarmPolicy(payload) {
  return axiosInstance.post('/api/v1/system/alarm-policies', payload)
}

export function updateAlarmPolicy(policyId, payload) {
  return axiosInstance.put(`/api/v1/system/alarm-policies/${encodeURIComponent(String(policyId))}`, payload)
}

export function deleteAlarmPolicy(policyId) {
  return axiosInstance.delete(`/api/v1/system/alarm-policies/${encodeURIComponent(String(policyId))}`)
}

export function ackAlarm(alarmId) {
  return axiosInstance.post(`/api/v1/system/alarms/${encodeURIComponent(String(alarmId))}/ack`)
}

export function closeAlarm(alarmId) {
  return axiosInstance.post(`/api/v1/system/alarms/${encodeURIComponent(String(alarmId))}/close`)
}

export function getSystemSettings() {
  return withLegacyReadFallback(
    () => axiosInstance.get('/api/v1/system/settings'),
    () => axiosInstance.get('/api/system/settings')
  )
}

export function saveSystemSettings(payload) {
  return axiosInstance.put('/api/v1/system/settings', payload)
}

export function resetSystemSettings(payload = {}) {
  return axiosInstance.post('/api/v1/system/settings/reset', payload)
}

export function getDatabaseOverview() {
  return withLegacyReadFallback(
    () => axiosInstance.get('/api/v1/system/database/overview'),
    () => axiosInstance.get('/system/database/overview')
  )
}
