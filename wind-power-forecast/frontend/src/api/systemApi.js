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

export function getSystemHardware() {
  return withLegacyFallback(
    () => axiosInstance.get('/api/v1/system/hardware'),
    () => axiosInstance.get('/api/system/hardware')
  )
}

export function getSystemSoftware() {
  return withLegacyFallback(
    () => axiosInstance.get('/api/v1/system/software'),
    () => axiosInstance.get('/api/system/software')
  )
}

export function getSystemRuntime() {
  return withLegacyFallback(
    () => axiosInstance.get('/api/v1/system/runtime'),
    () => axiosInstance.get('/api/system/runtime')
  )
}

export function getSystemLogs() {
  return withLegacyFallback(
    () => axiosInstance.get('/api/v1/system/logs'),
    () => axiosInstance.get('/api/system/logs')
  )
}

export function getAlarms(params = {}) {
  return withLegacyFallback(
    () => axiosInstance.get('/api/v1/system/alarms', { params }),
    () => axiosInstance.get('/api/system/alarms', { params })
  )
}

export function getAlarmNotifications() {
  return withLegacyFallback(
    () => axiosInstance.get('/api/v1/system/alarms/notifications'),
    () => axiosInstance.get('/api/system/alarms/notifications')
  )
}

export function getAlarmRules() {
  return withLegacyFallback(
    () => axiosInstance.get('/api/v1/system/alarm-rules'),
    () => axiosInstance.get('/api/system/alarm-rules')
  )
}

export function createAlarmRule(payload) {
  return withLegacyFallback(
    () => axiosInstance.post('/api/v1/system/alarm-rules', payload),
    () => axiosInstance.post('/api/system/alarm-rules', payload)
  )
}

export function updateAlarmRule(ruleId, payload) {
  return withLegacyFallback(
    () => axiosInstance.put(`/api/v1/system/alarm-rules/${encodeURIComponent(String(ruleId))}`, payload),
    () => axiosInstance.put(`/api/system/alarm-rules/${encodeURIComponent(String(ruleId))}`, payload)
  )
}

export function deleteAlarmRule(ruleId) {
  return withLegacyFallback(
    () => axiosInstance.delete(`/api/v1/system/alarm-rules/${encodeURIComponent(String(ruleId))}`),
    () => axiosInstance.delete(`/api/system/alarm-rules/${encodeURIComponent(String(ruleId))}`)
  )
}

export function getAlarmPolicies() {
  return withLegacyFallback(
    () => axiosInstance.get('/api/v1/system/alarm-policies'),
    () => axiosInstance.get('/api/system/alarm-policies')
  )
}

export function createAlarmPolicy(payload) {
  return withLegacyFallback(
    () => axiosInstance.post('/api/v1/system/alarm-policies', payload),
    () => axiosInstance.post('/api/system/alarm-policies', payload)
  )
}

export function updateAlarmPolicy(policyId, payload) {
  return withLegacyFallback(
    () => axiosInstance.put(`/api/v1/system/alarm-policies/${encodeURIComponent(String(policyId))}`, payload),
    () => axiosInstance.put(`/api/system/alarm-policies/${encodeURIComponent(String(policyId))}`, payload)
  )
}

export function deleteAlarmPolicy(policyId) {
  return withLegacyFallback(
    () => axiosInstance.delete(`/api/v1/system/alarm-policies/${encodeURIComponent(String(policyId))}`),
    () => axiosInstance.delete(`/api/system/alarm-policies/${encodeURIComponent(String(policyId))}`)
  )
}

export function ackAlarm(alarmId) {
  return withLegacyFallback(
    () => axiosInstance.post(`/api/v1/system/alarms/${encodeURIComponent(String(alarmId))}/ack`),
    () => axiosInstance.post(`/api/system/alarms/${encodeURIComponent(String(alarmId))}/ack`)
  )
}

export function closeAlarm(alarmId) {
  return withLegacyFallback(
    () => axiosInstance.post(`/api/v1/system/alarms/${encodeURIComponent(String(alarmId))}/close`),
    () => axiosInstance.post(`/api/system/alarms/${encodeURIComponent(String(alarmId))}/close`)
  )
}

export function getSystemSettings() {
  return withLegacyFallback(
    () => axiosInstance.get('/api/v1/system/settings'),
    () => axiosInstance.get('/api/system/settings')
  )
}

export function saveSystemSettings(payload) {
  return withLegacyFallback(
    () => axiosInstance.put('/api/v1/system/settings', payload),
    () => axiosInstance.put('/api/system/settings', payload)
  )
}

export function resetSystemSettings(payload = {}) {
  return withLegacyFallback(
    () => axiosInstance.post('/api/v1/system/settings/reset', payload),
    () => axiosInstance.post('/api/system/settings/reset', payload)
  )
}
