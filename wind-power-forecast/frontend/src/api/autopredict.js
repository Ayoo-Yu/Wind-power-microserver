import axios from 'axios'
import axiosInstance from './axios'

function shouldFallbackToLegacy(error) {
  const status = error?.response?.status
  return !error?.response || status === 404 || status === 405
}

export async function resurrectService() {
  try {
    return await axiosInstance.post('/api/v1/autopredict/resurrect')
  } catch (error) {
    if (shouldFallbackToLegacy(error)) {
      return axios({
        url: '/api/resurrect',
        method: 'post'
      })
    }
    throw error
  }
}
