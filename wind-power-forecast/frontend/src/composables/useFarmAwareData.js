// src/composables/useFarmAwareData.js
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import farmService from '../utils/farmService'
import {
  getFarmStatistics,
  getPredictionStatistics,
  getDatasets,
  getPredictions,
  getPowerCompareData
} from '../services/apiServiceEnhanced'

/**
 * 场站数据管理组合式函数
 * 提供场站感知的数据获取、缓存和管理功能
 */
export function useFarmAwareData(options = {}) {
  const {
    autoFetch = true,
    cacheKey = '',
    refreshInterval = null,
    enableCache = true
  } = options

  // 响应式数据
  const loading = ref(false)
  const error = ref(null)
  const data = ref(null)
  const currentFarm = ref(farmService.getCurrentFarm())

  // 缓存相关
  const cache = new Map()
  const lastFetchTime = ref(null)

  // 刷新计时器
  let refreshTimer = null

  // 计算属性
  const isLoading = computed(() => loading.value)
  const hasError = computed(() => error.value !== null)
  const isEmpty = computed(() => !data.value || (Array.isArray(data.value) && data.value.length === 0))
  const farmName = computed(() => {
    const farm = farmService.getFarmInfo(currentFarm.value)
    return farm ? farm.name : '未知场站'
  })

  /**
   * 清除缓存
   */
  const clearCache = () => {
    cache.clear()
    lastFetchTime.value = null
  }

  /**
   * 生成缓存键
   */
  const generateCacheKey = (prefix, farmCode) => {
    return `${prefix}_${farmCode}_${cacheKey}`
  }

  /**
   * 从缓存获取数据
   */
  const getFromCache = (key) => {
    if (!enableCache) return null

    const cached = cache.get(key)
    if (cached && Date.now() - cached.timestamp < 300000) { // 5分钟缓存
      return cached.data
    }
    return null
  }

  /**
   * 设置缓存
   */
  const setCache = (key, data) => {
    if (!enableCache) return

    cache.set(key, {
      data,
      timestamp: Date.now()
    })
  }

  /**
   * 通用数据获取函数
   */
  const fetchData = async (fetchFn, cachePrefix, params = {}) => {
    loading.value = true
    error.value = null

    try {
      const cacheKey = generateCacheKey(cachePrefix, currentFarm.value)
      const cachedData = getFromCache(cacheKey)

      if (cachedData) {
        data.value = cachedData
        return cachedData
      }

      const result = await fetchFn({
        ...params,
        farm_code: currentFarm.value
      })

      data.value = result.data || result
      setCache(cacheKey, data.value)
      lastFetchTime.value = Date.now()

      return data.value
    } catch (err) {
      error.value = err
      console.error('数据获取失败:', err)
      ElMessage.error(`获取${farmName.value}数据失败: ${err.message}`)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 手动刷新数据
   */
  const refresh = async () => {
    clearCache()
    await fetch()
  }

  /**
   * 获取场站统计数据
   */
  const fetchFarmStatistics = async (params = {}) => {
    return await fetchData(
      (params) => getFarmStatistics(currentFarm.value, params),
      'farm_statistics',
      params
    )
  }

  /**
   * 获取预测统计数据
   */
  const fetchPredictionStatistics = async (params = {}) => {
    return await fetchData(
      (params) => getPredictionStatistics(params),
      'prediction_statistics',
      params
    )
  }

  /**
   * 获取数据集列表
   */
  const fetchDatasets = async (params = {}) => {
    return await fetchData(
      (params) => getDatasets(params),
      'datasets',
      params
    )
  }

  /**
   * 获取预测结果
   */
  const fetchPredictions = async (params = {}) => {
    return await fetchData(
      (params) => getPredictions(params),
      'predictions',
      params
    )
  }

  /**
   * 获取功率对比数据
   */
  const fetchPowerCompareData = async (startTime, endTime, types = ['实测值', '预测值', '理论功率']) => {
    return await fetchData(
      () => getPowerCompareData(startTime, endTime, types),
      `power_compare_${startTime}_${endTime}`,
      { startTime, endTime, types }
    )
  }

  /**
   * 根据场站变化重新获取数据
   */
  const handleFarmChange = (farmCode) => {
    currentFarm.value = farmCode
    clearCache()
    if (autoFetch) {
      fetch()
    }
  }

  /**
   * 设置自动刷新
   */
  const setupAutoRefresh = () => {
    if (refreshInterval && refreshInterval > 0) {
      clearAutoRefresh()
      refreshTimer = setInterval(() => {
        if (autoFetch) {
          refresh()
        }
      }, refreshInterval)
    }
  }

  /**
   * 清除自动刷新
   */
  const clearAutoRefresh = () => {
    if (refreshTimer) {
      clearInterval(refreshTimer)
      refreshTimer = null
    }
  }

  /**
   * 通用获取函数（需要自定义实现）
   */
  const fetch = async () => {
    // 这个函数需要在使用时重写
    console.warn('fetch函数未实现，请在使用时重写')
  }

  // 监听场站变化
  watch(currentFarm, (newFarm, oldFarm) => {
    console.log(`场站从 ${oldFarm} 切换到 ${newFarm}`)
    if (newFarm !== oldFarm) {
      clearCache()
      if (autoFetch) {
        fetch()
      }
    }
  })

  // 生命周期钩子
  onMounted(() => {
    // 添加场站变化监听器
    farmService.addListener(handleFarmChange)

    // 自动获取数据
    if (autoFetch) {
      fetch()
    }

    // 设置自动刷新
    setupAutoRefresh()
  })

  onUnmounted(() => {
    // 清理监听器
    farmService.removeListener(handleFarmChange)

    // 清理定时器
    clearAutoRefresh()
  })

  return {
    // 状态
    loading: isLoading,
    error,
    data,
    currentFarm,
    lastFetchTime,

    // 计算属性
    isLoading,
    hasError,
    isEmpty,
    farmName,

    // 方法
    fetch,
    refresh,
    clearCache,
    fetchFarmStatistics,
    fetchPredictionStatistics,
    fetchDatasets,
    fetchPredictions,
    fetchPowerCompareData,
    setupAutoRefresh,
    clearAutoRefresh
  }
}

/**
 * 创建场站感知的数据表格组合式函数
 */
export function useFarmAwareTable(fetchFn, options = {}) {
  const {
    pageSize = 10,
    transformFn = null
  } = options

  const farmAwareData = useFarmAwareData({
    autoFetch: false,
    cacheKey: 'table_data'
  })

  // 表格相关状态
  const pagination = ref({
    currentPage: 1,
    pageSize: pageSize,
    total: 0
  })

  const filters = ref({})
  const sortConfig = ref({})

  // 计算分页数据
  const paginatedData = computed(() => {
    if (!farmAwareData.data.value) return []

    let result = farmAwareData.data.value

    // 应用转换函数
    if (transformFn) {
      result = transformFn(result)
    }

    // 更新总数
    pagination.value.total = result.length

    // 应用分页
    const start = (pagination.value.currentPage - 1) * pagination.value.pageSize
    const end = start + pagination.value.pageSize
    return result.slice(start, end)
  })

  /**
   * 获取表格数据
   */
  const fetchTableData = async (params = {}) => {
    const fetchParams = {
      ...filters.value,
      ...sortConfig.value,
      page: pagination.value.currentPage,
      page_size: pagination.value.pageSize,
      ...params
    }

    await farmAwareData.fetchData(fetchFn, 'table_data', fetchParams)
  }

  /**
   * 处理分页变化
   */
  const handlePageChange = (page) => {
    pagination.value.currentPage = page
    fetchTableData()
  }

  /**
   * 处理每页条数变化
   */
  const handleSizeChange = (size) => {
    pagination.value.pageSize = size
    pagination.value.currentPage = 1
    fetchTableData()
  }

  /**
   * 处理排序变化
   */
  const handleSortChange = (sort) => {
    sortConfig.value = sort
    fetchTableData()
  }

  /**
   * 处理筛选变化
   */
  const handleFilterChange = (newFilters) => {
    filters.value = { ...newFilters }
    pagination.value.currentPage = 1
    fetchTableData()
  }

  /**
   * 重置表格
   */
  const resetTable = () => {
    pagination.value.currentPage = 1
    filters.value = {}
    sortConfig.value = {}
    farmAwareData.clearCache()
    fetchTableData()
  }

  return {
    // 继承所有 useFarmAwareData 的属性和方法
    ...farmAwareData,

    // 表格特有的属性和方法
    pagination,
    filters,
    sortConfig,
    paginatedData,
    fetchTableData,
    handlePageChange,
    handleSizeChange,
    handleSortChange,
    handleFilterChange,
    resetTable
  }
}
