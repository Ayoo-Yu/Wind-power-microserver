import axios from './axios'

import { withLegacyReadFallback } from './legacyFallback.cjs'

const authGet = (path) => withLegacyReadFallback(
  () => axios.get(`/api/v1/auth/${path}`),
  () => axios.get(`/api/auth/${path}`)
)

const authPost = (path, payload) => axios.post(`/api/v1/auth/${path}`, payload)

const authPut = (path, payload) => axios.put(`/api/v1/auth/${path}`, payload)

const authDelete = (path) => axios.delete(`/api/v1/auth/${path}`)

const authGetWithParams = (path, params = {}) => withLegacyReadFallback(
  () => axios.get(`/api/v1/auth/${path}`, { params }),
  () => axios.get(`/api/auth/${path}`, { params })
)

export const login = async (username, password) => {
  const response = await authPost('login', { username, password })
  return response.data
}

export const getCurrentUser = async () => {
  const response = await authGet('me')
  const rolePermissions = Array.isArray(response.data?.role?.permissions)
    ? response.data.role.permissions
    : Array.isArray(response.data?.role?.permissions?.permissions)
      ? response.data.role.permissions.permissions
      : []
  try {
    const metaResponse = await authGet('me/profile-meta')
    return {
      ...response.data,
      permissions: rolePermissions,
      phone: metaResponse.data?.phone || '',
      stations: Array.isArray(metaResponse.data?.stations) ? metaResponse.data.stations : ['__ALL__']
    }
  } catch (error) {
    return {
      ...response.data,
      permissions: rolePermissions,
      phone: '',
      stations: ['__ALL__']
    }
  }
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

export const getUsersMeta = async () => {
  const response = await authGet('users-meta')
  return response.data
}

export const updateUserMeta = async (userId, payload) => {
  const response = await authPut(`users/${userId}/meta`, payload)
  return response.data
}

export const deleteUserMeta = async (userId) => {
  const response = await authDelete(`users/${userId}/meta`)
  return response.data
}

export const getAuditLogs = async (params = {}) => {
  const response = await authGetWithParams('audit-logs', params)
  return response.data
}

export const createAuditLog = async (payload) => {
  const response = await authPost('audit-logs', payload)
  return response.data
}
