import axios from './axios'

const shouldFallbackToLegacy = (error) => {
  const status = error?.response?.status
  return !error?.response || status === 404 || status === 405
}

const withLegacyFallback = async (v1Call, legacyCall) => {
  try {
    return await v1Call()
  } catch (error) {
    if (shouldFallbackToLegacy(error)) {
      return legacyCall()
    }
    throw error
  }
}

const authGet = (path) => withLegacyFallback(
  () => axios.get(`/api/v1/auth/${path}`),
  () => axios.get(`/api/auth/${path}`)
)

const authPost = (path, payload) => withLegacyFallback(
  () => axios.post(`/api/v1/auth/${path}`, payload),
  () => axios.post(`/api/auth/${path}`, payload)
)

const authPut = (path, payload) => withLegacyFallback(
  () => axios.put(`/api/v1/auth/${path}`, payload),
  () => axios.put(`/api/auth/${path}`, payload)
)

const authDelete = (path) => withLegacyFallback(
  () => axios.delete(`/api/v1/auth/${path}`),
  () => axios.delete(`/api/auth/${path}`)
)

export const login = async (username, password) => {
  const response = await authPost('login', { username, password })
  return response.data
}

export const getCurrentUser = async () => {
  const response = await authGet('me')
  return response.data
}

export const changePassword = async (username, currentPassword, newPassword) => {
  const response = await authPost('change-password', {
    username,
    current_password: currentPassword,
    new_password: newPassword
  })
  return response.data
}

export const getUsers = async () => {
  const response = await authGet('users')
  return response.data
}

export const createUser = async (userData) => {
  const response = await authPost('users', userData)
  return response.data
}

export const updateUser = async (userId, userData) => {
  const response = await authPut(`users/${userId}`, userData)
  return response.data
}

export const deleteUser = async (userId) => {
  const response = await authDelete(`users/${userId}`)
  return response.data
}

export const resetUserPassword = async (userId, newPassword) => {
  const response = await authPost(`users/${userId}/reset-password`, {
    new_password: newPassword
  })
  return response.data
}

export const getRoles = async () => {
  const response = await authGet('roles')
  return response.data
}

export const createRole = async (roleData) => {
  const response = await authPost('roles', roleData)
  return response.data
}

export const updateRole = async (roleId, roleData) => {
  const response = await authPut(`roles/${roleId}`, roleData)
  return response.data
}

export const deleteRole = async (roleId) => {
  const response = await authDelete(`roles/${roleId}`)
  return response.data
}
