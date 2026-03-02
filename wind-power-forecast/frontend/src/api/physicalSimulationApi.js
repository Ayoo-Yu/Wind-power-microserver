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

export function getSimulationConditions(params = {}) {
  return withLegacyFallback(
    () => axiosInstance.get('/api/v1/physical-simulation/conditions', { params }),
    () => axiosInstance.get('/physical_simulation/conditions', { params })
  )
}

export function getSimulationTurbines(params = {}) {
  return withLegacyFallback(
    () => axiosInstance.get('/api/v1/physical-simulation/turbines', { params }),
    () => axiosInstance.get('/physical_simulation/turbines', { params })
  )
}

export function getSimulationReadings(params = {}) {
  return withLegacyFallback(
    () => axiosInstance.get('/api/v1/physical-simulation/readings', { params }),
    () => axiosInstance.get('/physical_simulation/readings', { params })
  )
}
