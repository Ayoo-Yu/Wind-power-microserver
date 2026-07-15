import axiosInstance from './axios'

export async function listConnections() {
  const response = await axiosInstance.get('/scada/connections')
  return response?.data?.data || []
}

export async function getConnection(id) {
  const response = await axiosInstance.get(`/scada/connections/${id}`)
  return response?.data?.data
}

export async function createConnection(payload) {
  const response = await axiosInstance.post('/scada/connections', payload)
  return response?.data?.data
}

export async function updateConnection(id, payload) {
  const response = await axiosInstance.put(`/scada/connections/${id}`, payload)
  return response?.data?.data
}

export async function deleteConnection(id) {
  const response = await axiosInstance.delete(`/scada/connections/${id}`)
  return response?.data
}

export async function startConnection(id) {
  const response = await axiosInstance.post(`/scada/connections/${id}/start`)
  return response?.data
}

export async function stopConnection(id) {
  const response = await axiosInstance.post(`/scada/connections/${id}/stop`)
  return response?.data
}

export async function restartConnection(id) {
  const response = await axiosInstance.post(`/scada/connections/${id}/restart`)
  return response?.data
}

export async function testConnection(id) {
  const response = await axiosInstance.post(`/scada/connections/${id}/test`)
  return response?.data
}

export async function getConnectionData(id, limit = 20) {
  const response = await axiosInstance.get(`/scada/connections/${id}/data`, { params: { limit } })
  return response?.data?.data || []
}

export async function getAvailableFarms() {
  const response = await axiosInstance.get('/scada/connections/farms')
  return response?.data?.data || []
}

export async function getHealth() {
  const response = await axiosInstance.get('/api/v1/scada/health')
  return response?.data || { availability: 'unavailable', connections: [] }
}
