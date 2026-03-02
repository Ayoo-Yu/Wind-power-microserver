// src/services/apiServiceEnhanced.js
import axios from 'axios'
import farmService from '../utils/farmService'

let backendBaseUrl
if (window.location.hostname !== 'localhost') {
  backendBaseUrl = `http://${window.location.hostname}:5000`
} else {
  backendBaseUrl = 'http://localhost:5000'
}

const createFarmAwareData = (data = {}) => ({
  ...data,
  farm_code: farmService.getCurrentFarm()
})

const createFarmAwareConfig = (config = {}) => {
  const farmAwareConfig = { ...config }
  if (!farmAwareConfig.params) {
    farmAwareConfig.params = {}
  }
  farmAwareConfig.params.farm_code = farmService.getCurrentFarm()
  return farmAwareConfig
}

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
  return axios.post(`${backendBaseUrl}/power-compare/data`, requestData)
}

export const getDatasets = async (params = {}) => {
  const config = createFarmAwareConfig(params)
  return axios.get(`${backendBaseUrl}/api/datasets`, config)
}

export const getDatasetById = async (datasetId) => {
  const config = createFarmAwareConfig()
  return axios.get(`${backendBaseUrl}/api/datasets/${datasetId}`, config)
}

export const getPredictions = async (params = {}) => {
  const config = createFarmAwareConfig(params)
  return axios.get(`${backendBaseUrl}/api/predictions`, config)
}

export const getPredictionById = async (predictionId) => {
  const config = createFarmAwareConfig()
  return axios.get(`${backendBaseUrl}/api/predictions/${predictionId}`, config)
}

export const getSystemStatus = async () => {
  const config = createFarmAwareConfig()
  return axios.get(`${backendBaseUrl}/system/status`, config)
}

export const getFarmList = async () => {
  return axios.get(`${backendBaseUrl}/api/farms`)
}

export const getFarmInfo = async (farmCode) => {
  return axios.get(`${backendBaseUrl}/api/farms/${farmCode}`)
}

export const getFarmStatistics = async (farmCode, params = {}) => {
  const config = createFarmAwareConfig(params)
  return axios.get(`${backendBaseUrl}/api/farms/${farmCode}/statistics`, config)
}

export const getPredictionStatistics = async (params = {}) => {
  const config = createFarmAwareConfig(params)
  return axios.get(`${backendBaseUrl}/api/statistics/predictions`, config)
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
