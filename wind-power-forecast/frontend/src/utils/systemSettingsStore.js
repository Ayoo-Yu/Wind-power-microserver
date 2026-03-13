const STORAGE_KEY = 'system_settings_v1'

const DEFAULT_SETTINGS = {
  holidays: [
    { date: '2026-10-01', note: '国庆节' }
  ],
  dict: {
    turbineModels: 'GW121, GW155, EN171',
    vendors: '金风, 远景, 明阳'
  },
  params: {
    retentionMonths: 12,
    logRetentionDays: 180,
    diskAlertPercent: 85
  }
}

export function getDefaultSystemSettings() {
  return JSON.parse(JSON.stringify(DEFAULT_SETTINGS))
}

export function readSystemSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : null
    if (!parsed || typeof parsed !== 'object') {
      return getDefaultSystemSettings()
    }

    return {
      holidays: Array.isArray(parsed.holidays) ? parsed.holidays : getDefaultSystemSettings().holidays,
      dict: {
        ...getDefaultSystemSettings().dict,
        ...(parsed.dict || {})
      },
      params: {
        ...getDefaultSystemSettings().params,
        ...(parsed.params || {})
      }
    }
  } catch (error) {
    console.warn('读取系统基础配置失败', error)
    return getDefaultSystemSettings()
  }
}

export function saveSystemSettings(payload) {
  const data = {
    ...getDefaultSystemSettings(),
    ...(payload || {})
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  return data
}
