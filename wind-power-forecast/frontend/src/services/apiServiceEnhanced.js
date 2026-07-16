// src/services/apiServiceEnhanced.js
import axiosInstance from '../api/axios'
import { getPowerCompareData as getPowerCompareDataCompat } from '../api/powerCompareApi'
import { withLegacyReadFallback } from '../api/legacyFallback.cjs'
import farmService from '../utils/farmService'

const createFarmAwareData = (data = {}) => ({
  ...data,
  farm_code: farmService.getCurrentFarm()
})

const createFarmAwareConfig = (params = {}, config = {}) => ({
  ...config,
  params: {
    ...(config.params || {}),
    ...(params || {}),
    farm_code: farmService.getCurrentFarm()
  }
})

export const getPowerCompareData = async (
  startTime,
  endTime,
  types = ['实测值', '预测值', '理论功率']
) => {
  const requestData = createFarmAwareData({
    start: startTime,
    end: endTime,
    types
  })
  return getPowerCompareDataCompat(requestData)
}

export const getDatasets = async (params = {}) => {
  return axiosInstance.get('/api/datasets', createFarmAwareConfig(params))
}

export const getDatasetById = async (datasetId) => {
  return axiosInstance.get(`/api/datasets/${datasetId}`, createFarmAwareConfig())
}

export const getPredictions = async (params = {}) => {
  return axiosInstance.get('/api/predictions', createFarmAwareConfig(params))
}

export const getPredictionById = async (predictionId) => {
  return axiosInstance.get(`/api/predictions/${predictionId}`, createFarmAwareConfig())
}

export const getSystemStatus = async () => {
  return axiosInstance.get('/system/status', createFarmAwareConfig())
}

export const getFarmList = async () => {
  return withLegacyReadFallback(
    () => axiosInstance.get('/api/v1/farms'),
    () => axiosInstance.get('/api/farms')
  )
}

export const getFarmInfo = async (farmCode) => {
  const normalizedFarmCode = String(farmCode || '').trim()
  return withLegacyReadFallback(
    () => axiosInstance.get(`/api/v1/farms/${encodeURIComponent(normalizedFarmCode)}`),
    () => axiosInstance.get(`/api/farms/${encodeURIComponent(normalizedFarmCode)}`)
  )
}

export const getFarmStatistics = async (farmCode, params = {}) => {
  const normalizedFarmCode = String(farmCode || '').trim()
  const config = createFarmAwareConfig(params)
  return withLegacyReadFallback(
    () => axiosInstance.get(`/api/v1/farms/${encodeURIComponent(normalizedFarmCode)}/stats`, config),
    () => axiosInstance.get(`/api/farms/${encodeURIComponent(normalizedFarmCode)}/stats`, config)
  )
}

export const getPredictionStatistics = async (params = {}) => {
  return axiosInstance.get('/api/statistics/predictions', createFarmAwareConfig(params))
}

export const filterCurrentFarmData = (data) => farmService.filterCurrentFarmData(data)

export const addFarmParams = (params = {}) => farmService.addFarmParams(params)

export const getCurrentFarm = () => farmService.getCurrentFarm()

export const setCurrentFarm = (farmCode) => {
  farmService.setCurrentFarm(farmCode)
}

export const onFarmChange = (callback) => {
  farmService.addListener(callback)
}

export const offFarmChange = (callback) => {
  farmService.removeListener(callback)
}
