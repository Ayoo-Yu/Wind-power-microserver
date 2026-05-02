// src/utils/farmService.js
import { getAutoPredictFarms, getReportFarms, getFarms } from '../api/farmApi'
/**
 * 场站管理服务
 * 提供场站选择、状态管理和数据隔离功能
 */

class FarmService {
  constructor() {
    this.currentFarm = localStorage.getItem('selectedFarm') || ''
    this.availableFarms = []
    this.farmsLoaded = false
    this.listeners = []
  }

  /**
   * 获取当前选中的场站
   */
  getCurrentFarm() {
    return this.currentFarm
  }

  /**
   * 设置当前场站
   */
  setCurrentFarm(farmCode) {
    if (!farmCode || typeof farmCode !== 'string') {
      return
    }
    const normalizedCode = farmCode.trim()
    if (!normalizedCode) {
      return
    }

    if (this.currentFarm !== normalizedCode) {
      this.currentFarm = normalizedCode
      localStorage.setItem('selectedFarm', normalizedCode)
      this.notifyListeners(normalizedCode)
    }
  }

  /**
   * 获取所有可用场站
   */
  getAvailableFarms() {
    return this.availableFarms
  }

  getCurrentUserScopeCodes() {
    try {
      const currentUser = JSON.parse(localStorage.getItem('user') || '{}')
      const stations = Array.isArray(currentUser?.stations) ? currentUser.stations : []
      if (stations.includes('__ALL__')) return null
      return stations.length > 0 ? stations : null
    } catch (error) {
      return null
    }
  }

  applyUserScope(farms = []) {
    const scopeCodes = this.getCurrentUserScopeCodes()
    if (!scopeCodes) return farms
    const whitelist = new Set(scopeCodes.map(item => String(item).toLowerCase()))
    const filtered = farms.filter(farm => whitelist.has(String(farm.code).toLowerCase()))
    return filtered.length > 0 ? filtered : farms
  }

  /**
   * 使用新列表覆盖当前场站列表，并校验当前场站是否有效
   */
  setAvailableFarms(farms) {
    if (!Array.isArray(farms) || farms.length === 0) {
      this.availableFarms = []
      this.farmsLoaded = false
    } else {
      this.availableFarms = this.applyUserScope(farms)
    }

    const exists = this.availableFarms.some(f => f.code === this.currentFarm)
    if (!exists) {
      this.setCurrentFarm(this.availableFarms[0]?.code || '')
    }
  }

  /**
   * 从后端加载可用场站列表
   */
  async loadAvailableFarms(forceReload = false) {
    if (this.farmsLoaded && !forceReload) {
      return this.availableFarms
    }

    try {
      const normalizeFarmCode = (value) => {
        if (value === undefined || value === null) {
          return null
        }
        const code = String(value).trim()
        return code || null
      }

      const mapFarms = (farms = []) => farms
        .filter(farm => farm && farm.farm_code)
        .map(farm => {
          const code = normalizeFarmCode(farm.farm_code)
          if (!code) {
            return null
          }
          const farmName = typeof farm.farm_name === 'string' ? farm.farm_name.trim() : ''
          return {
            code,
            name: farmName || code,
            capacity: Number(farm.capacity) || 0
          }
        })
        .filter(Boolean)

      const dedupeByCode = (farms = []) => {
        const seen = new Set()
        const result = []
        farms.forEach((farm) => {
          const key = farm.code.toLowerCase()
          if (seen.has(key)) {
            return
          }
          seen.add(key)
          result.push(farm)
        })
        return result
      }

      let autopredictFarms = []
      let reportFarms = []
      let generalFarms = []

      try {
        autopredictFarms = await getAutoPredictFarms()
      } catch (autopredictError) {
        console.warn('自动预测后端场站接口不可用', autopredictError)
      }

      try {
        reportFarms = await getReportFarms()
      } catch (reportError) {
        console.warn('主后端场站接口不可用', reportError)
      }

      try {
        generalFarms = await getFarms()
      } catch (generalError) {
        console.warn('通用场站接口不可用', generalError)
      }

      const mappedAutopredictFarms = mapFarms(autopredictFarms)
      const mappedReportFarms = mapFarms(reportFarms)
      const mappedGeneralFarms = mapFarms(generalFarms)

      let mappedFarms = []
      if (mappedAutopredictFarms.length > 0) {
        const reportNameByCode = new Map()
        mappedGeneralFarms.forEach((farm) => reportNameByCode.set(farm.code.toLowerCase(), farm.name))
        mappedReportFarms.forEach((farm) => reportNameByCode.set(farm.code.toLowerCase(), farm.name))
        mappedFarms = mappedAutopredictFarms.map((farm) => ({
          code: farm.code,
          name: reportNameByCode.get(farm.code.toLowerCase()) || farm.name,
          capacity: farm.capacity
        }))
      } else if (mappedReportFarms.length > 0) {
        mappedFarms = mappedReportFarms
      } else if (mappedGeneralFarms.length > 0) {
        mappedFarms = mappedGeneralFarms
      }

      mappedFarms = dedupeByCode(mappedFarms)

      if (mappedFarms.length > 0) {
        this.setAvailableFarms(mappedFarms)
        this.farmsLoaded = true
      } else {
        this.availableFarms = []
        this.farmsLoaded = false
      }
    } catch (error) {
      console.error('加载场站列表失败', error)
      this.availableFarms = []
      this.farmsLoaded = false
    }

    return this.availableFarms
  }

  /**
   * 获取场站信息
   */
  getFarmInfo(farmCode) {
    const farms = this.getAvailableFarms()
    return farms.find(farm => farm.code === farmCode) || null
  }

  /**
   * 添加场站变化监听器
   */
  addListener(callback) {
    this.listeners.push(callback)
  }

  /**
   * 移除场站变化监听器
   */
  removeListener(callback) {
    const index = this.listeners.indexOf(callback)
    if (index > -1) {
      this.listeners.splice(index, 1)
    }
  }

  /**
   * 通知所有监听器
   */
  notifyListeners(farmCode) {
    this.listeners.forEach(callback => {
      try {
        callback(farmCode)
      } catch (error) {
        console.error('场站监听器执行失败', error)
      }
    })
  }

  /**
   * 为 API 请求添加场站参数
   */
  addFarmParams(params = {}) {
    return {
      ...params,
      farm_code: this.currentFarm
    }
  }

  /**
   * 检查数据是否属于当前场站
   */
  isCurrentFarmData(data) {
    if (!data || !data.farm_code) {
      return false
    }
    return data.farm_code === this.currentFarm
  }

  /**
   * 过滤当前场站的数据
   */
  filterCurrentFarmData(dataArray) {
    if (!Array.isArray(dataArray)) {
      return []
    }
    return dataArray.filter(item => this.isCurrentFarmData(item))
  }

  /**
   * 重置到第一个场站
   */
  resetToDefault() {
    this.setCurrentFarm(this.availableFarms[0]?.code || '')
  }
}

// 创建单例实例
const farmService = new FarmService()

// 导出单例
export default farmService

// 导出类型定义
export class FarmInfo {
  constructor(code, name) {
    this.code = code
    this.name = name
  }
}
