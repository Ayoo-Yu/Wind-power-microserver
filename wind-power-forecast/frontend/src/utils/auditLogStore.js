import { createAuditLog, getAuditLogs } from '../api/auth'

export const listAuditLogs = async (params = {}) => {
  try {
    const data = await getAuditLogs(params)
    return data && typeof data === 'object'
      ? data
      : { logs: [], total: 0, page: 1, per_page: 20, pages: 0 }
  } catch (error) {
    console.warn('加载后端审计日志失败', error)
    return { logs: [], total: 0, page: 1, per_page: 20, pages: 0 }
  }
}

export const appendAuditLog = async (payload = {}) => {
  try {
    const currentUser = JSON.parse(localStorage.getItem('user') || '{}')
    const response = await createAuditLog({
      operator: payload.operator || currentUser.username || 'unknown',
      ipAddress: payload.ipAddress || '-',
      module: payload.module || '系统',
      operationType: payload.operationType || '操作',
      details: payload.details || '',
      result: payload.result || '成功'
    })
    return response?.log || response
  } catch (error) {
    console.warn('写入后端审计日志失败', error)
    return null
  }
}
