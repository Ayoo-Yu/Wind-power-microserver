import axiosInstance from './axios'

import { withLegacyReadFallback } from './legacyFallback.cjs'

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
  const response = await withLegacyReadFallback(
    () => axiosInstance.get('/api/v1/autopredict/farms'),
    () => axiosInstance.get('/api/farms')
  )
  return unwrapList(response?.data)
}

export async function getReportFarms() {
  const response = await withLegacyReadFallback(
    () => axiosInstance.get('/api/v1/report/farms'),
    () => axiosInstance.get('/api/report/farms')
  )
  return unwrapList(response?.data)
}

export async function getFarms() {
  const response = await withLegacyReadFallback(
    () => axiosInstance.get('/api/v1/farms', { _silent: true }),
    () => axiosInstance.get('/api/farms', { _silent: true })
  )
  return unwrapList(response?.data)
}

export async function createFarm(payload) {
  const response = await axiosInstance.post('/api/v1/farms', payload)
  return response?.data
}

export async function updateFarm(farmCode, payload) {
  const response = await axiosInstance.put(`/api/v1/farms/${farmCode}`, payload)
  return response?.data
}

export async function deleteFarm(farmCode) {
  const response = await axiosInstance.delete(`/api/v1/farms/${farmCode}`)
  return response?.data
}

export async function toggleFarm(farmCode) {
  const response = await axiosInstance.post(`/api/v1/farms/${farmCode}/toggle`)
  return response?.data
}
