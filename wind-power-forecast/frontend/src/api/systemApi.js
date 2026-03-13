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
