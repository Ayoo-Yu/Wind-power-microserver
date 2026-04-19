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

function unwrapList(payload) {
  if (Array.isArray(payload)) {
    return payload
  }
  if (Array.isArray(payload?.data)) {
    return payload.data
  }
  return []
}

export async function getAutoPredictFarms() {
  const response = await withLegacyFallback(
    () => axiosInstance.get('/api/v1/autopredict/farms'),
    () => axiosInstance.get('/api/farms')
  )
  return unwrapList(response?.data)
}

export async function getReportFarms() {
  const response = await withLegacyFallback(
    () => axiosInstance.get('/api/v1/report/farms'),
    () => axiosInstance.get('/api/report/farms')
  )
  return unwrapList(response?.data)
}

export async function getFarms() {
  const response = await withLegacyFallback(
    () => axiosInstance.get('/api/v1/farms', { _silent: true }),
    () => axiosInstance.get('/api/farms', { _silent: true })
  )
  return unwrapList(response?.data)
}

export async function createFarm(payload) {
  const response = await withLegacyFallback(
    () => axiosInstance.post('/api/v1/farms', payload),
    () => axiosInstance.post('/api/farms', payload)
  )
  return response?.data
}

export async function updateFarm(farmCode, payload) {
  const response = await withLegacyFallback(
    () => axiosInstance.put(`/api/v1/farms/${farmCode}`, payload),
    () => axiosInstance.put(`/api/farms/${farmCode}`, payload)
  )
  return response?.data
}

export async function deleteFarm(farmCode) {
  const response = await withLegacyFallback(
    () => axiosInstance.delete(`/api/v1/farms/${farmCode}`),
    () => axiosInstance.delete(`/api/farms/${farmCode}`)
  )
  return response?.data
}

export async function toggleFarm(farmCode) {
  const response = await withLegacyFallback(
    () => axiosInstance.post(`/api/v1/farms/${farmCode}/toggle`),
    () => axiosInstance.post(`/api/farms/${farmCode}/toggle`)
  )
  return response?.data
}
