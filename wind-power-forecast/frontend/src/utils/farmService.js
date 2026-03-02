// src/utils/farmService.js
import axiosInstance from '../api/axios'
/**
 * 场站管理服务
 * 提供场站选择、状态管理和数据隔离功能
 */

class FarmService {
  constructor() {
    this.currentFarm = localStorage.getItem('selectedFarm') || 'DEFAULT_FARM'
    this.availableFarms = [
      { code: 'DEFAULT_FARM', name: '默认风场' }
    ]
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

      // 通知所有监听器
      this.notifyListeners(normalizedCode)
    }
  }

  /**
   * 获取所有可用场站
   */
  getAvailableFarms() {
    return this.availableFarms
  }

  /**
   * 使用新列表覆盖当前场站列表，并校验当前场站是否有效
   */
  setAvailableFarms(farms) {
    if (!Array.isArray(farms) || farms.length === 0) {
      this.availableFarms = [{ code: 'DEFAULT_FARM', name: '默认风场' }]
      this.farmsLoaded = false
    } else {
      this.availableFarms = farms
    }

    const exists = this.availableFarms.some(f => f.code === this.currentFarm)
    if (!exists) {
      this.setCurrentFarm(this.availableFarms[0].code)
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
      const fetchFarms = async (url) => {
        const response = await axiosInstance.get(url)
        const payload = response?.data
        const farms = Array.isArray(payload) ? payload : payload?.data
        if (!Array.isArray(farms)) {
          throw new Error('场站列表返回格式错误')
        }
        return farms
      }

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
            name: farmName || code
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

      try {
        autopredictFarms = await fetchFarms('/api/v1/autopredict/farms')
      } catch (autopredictError) {
        console.warn('自动预测后端场站接口不可用', autopredictError)
      }

      try {
        reportFarms = await fetchFarms('/api/report/farms')
      } catch (reportError) {
        console.warn('主后端场站接口不可用', reportError)
      }

      const mappedAutopredictFarms = mapFarms(autopredictFarms)
      const mappedReportFarms = mapFarms(reportFarms)

      let mappedFarms = []
      if (mappedAutopredictFarms.length > 0) {
        const reportNameByCode = new Map(
          mappedReportFarms.map(farm => [farm.code.toLowerCase(), farm.name])
        )
        mappedFarms = mappedAutopredictFarms.map((farm) => ({
          code: farm.code,
          name: reportNameByCode.get(farm.code.toLowerCase()) || farm.name
        }))
      } else if (mappedReportFarms.length > 0) {
        mappedFarms = mappedReportFarms
      }

      mappedFarms = dedupeByCode(mappedFarms)

      if (mappedFarms.length > 0) {
        this.setAvailableFarms(mappedFarms)
        this.farmsLoaded = true
      } else {
        this.setAvailableFarms([{ code: 'DEFAULT_FARM', name: '默认风场' }])
        this.farmsLoaded = false
      }
    } catch (error) {
      console.error('加载场站列表失败，使用本地默认列表', error)
      this.setAvailableFarms([{ code: 'DEFAULT_FARM', name: '默认风场' }])
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
   * 重置到默认场站
   */
  resetToDefault() {
    const defaultFarm = this.availableFarms.find(f => f.code === 'DEFAULT_FARM')
    this.setCurrentFarm(defaultFarm ? 'DEFAULT_FARM' : this.availableFarms[0].code)
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

