import axiosInstance from './axios'

export function getCapabilities() {
  return axiosInstance.get('/api/v1/system/capabilities', { _silent: true })
}
