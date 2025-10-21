// src/utils/farmService.js

/**
 * 场站管理服务
 * 提供场站选择、状态管理和数据隔离功能
 */

class FarmService {
  constructor() {
    this.currentFarm = localStorage.getItem('selectedFarm') || 'DEFAULT_FARM'
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
    if (this.currentFarm !== farmCode) {
      this.currentFarm = farmCode
      localStorage.setItem('selectedFarm', farmCode)

      // 通知所有监听器
      this.notifyListeners(farmCode)
    }
  }

  /**
   * 获取所有可用场站
   */
  getAvailableFarms() {
    return [
      { code: 'DEFAULT_FARM', name: '默认风场' },
      { code: 'zyx01', name: '中扬新1号风场' },
      { code: 'zyx02', name: '中扬新2号风场' }
    ]
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
        console.error('场站监听器执行失败:', error)
      }
    })
  }

  /**
   * 为API请求添加场站参数
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
    this.setCurrentFarm('DEFAULT_FARM')
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