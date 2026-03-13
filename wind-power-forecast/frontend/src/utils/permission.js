const ADMIN_ROLE_NAMES = ['系统管理员', 'admin', 'Administrator']

export const getStoredUser = () => {
  try {
    const raw = localStorage.getItem('user')
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export const normalizePermissions = (user) => {
  if (!user) return []

  if (Array.isArray(user.permissions)) {
    return user.permissions
  }

  if (Array.isArray(user.permissions?.permissions)) {
    return user.permissions.permissions
  }

  return []
}

export const isSuperAdmin = (user) => {
  if (!user) return false

  const role = user.role
  const roleName = typeof role === 'string' ? role : role?.name
  if (ADMIN_ROLE_NAMES.includes(roleName)) {
    return true
  }

  return normalizePermissions(user).includes('admin')
}

export const hasPermission = (user, permission) => {
  if (!permission) return true
  if (isSuperAdmin(user)) return true
  return normalizePermissions(user).includes(permission)
}

export const hasAnyPermission = (user, permissions = []) => {
  if (!Array.isArray(permissions) || permissions.length === 0) {
    return true
  }

  return permissions.some(permission => hasPermission(user, permission))
}
