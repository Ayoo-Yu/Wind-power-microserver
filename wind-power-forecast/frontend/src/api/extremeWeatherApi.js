import axiosInstance from './axios'

const BASE = '/api/extreme-weather'

export function getWeatherStatus(farmCode) {
  return axiosInstance.get(`${BASE}/status`, { params: { farm_code: farmCode } })
}

export function getThresholds() {
  return axiosInstance.get(`${BASE}/thresholds`)
}

export function updateThresholds(thresholds) {
  return axiosInstance.put(`${BASE}/thresholds`, thresholds)
}

export function getWeatherHistory(farmCode, page = 1) {
  return axiosInstance.get(`${BASE}/history`, { params: { farm_code: farmCode, page } })
}
