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
    () => axiosInstance.get('/api/v1/farms'),
    () => axiosInstance.get('/api/farms')
  )
  return unwrapList(response?.data)
}
