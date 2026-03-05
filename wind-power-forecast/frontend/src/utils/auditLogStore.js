const STORAGE_KEY = 'audit_logs_v1'

const readLogs = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch (error) {
    return []
  }
}

const writeLogs = (logs) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.isArray(logs) ? logs : []))
}

export const listAuditLogs = () => readLogs()

export const appendAuditLog = (payload = {}) => {
  const currentUser = JSON.parse(localStorage.getItem('user') || '{}')
  const logs = readLogs()
  const next = {
    id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    operationTime: new Date().toISOString(),
    operator: payload.operator || currentUser.username || 'unknown',
    ipAddress: payload.ipAddress || '-',
    module: payload.module || '系统',
    operationType: payload.operationType || '操作',
    details: payload.details || '',
    result: payload.result || '成功'
  }
  logs.unshift(next)
  writeLogs(logs.slice(0, 5000))
  return next
}
