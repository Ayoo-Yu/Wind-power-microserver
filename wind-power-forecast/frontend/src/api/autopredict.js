import axiosInstance from './axios'

export function resurrectService() {
  return axiosInstance.post('resurrect')
} 