import axiosInstance from './axios'

export function getOperationsOverview(farmCode = '') {
  const params = farmCode ? { farm_code: farmCode } : {}
  return axiosInstance.get('/api/v1/operations/overview', { params })
}

export function getPredictionInputSnapshots(params = {}) {
  return axiosInstance.get('/api/v1/operations/prediction-inputs', { params })
}

export function approveModelVersion(versionId) {
  return axiosInstance.post(`/api/model_versions/${encodeURIComponent(String(versionId))}/approve`)
}

export function rejectModelVersion(versionId, reason) {
  return axiosInstance.post(
    `/api/model_versions/${encodeURIComponent(String(versionId))}/reject`,
    { reason }
  )
}

export function rollbackModelVersion(versionId) {
  return axiosInstance.post(`/api/model_versions/${encodeURIComponent(String(versionId))}/rollback`)
}
