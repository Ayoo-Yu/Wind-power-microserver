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

export function getFleetMetrics(payload) {
  return withLegacyFallback(
    () => axiosInstance.post('/api/v1/power-compare/fleet_metrics', payload),
    () => axiosInstance.post('/power-compare/fleet_metrics', payload)
  )
}

export function getFleetSeries(payload) {
  return withLegacyFallback(
    () => axiosInstance.post('/api/v1/power-compare/fleet_series', payload),
    () => axiosInstance.post('/power-compare/fleet_series', payload)
  )
}

export function getPowerCompareData(payload) {
  return withLegacyFallback(
    () => axiosInstance.post('/api/v1/power-compare/data', payload, { _silent: true }),
    () => axiosInstance.post('/power-compare/data', payload, { _silent: true })
  )
}
