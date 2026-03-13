// src/services/websocketService.js
import { onMounted, onUnmounted, ref } from 'vue'
import { io } from 'socket.io-client'
import farmService from '../utils/farmService'

/**
 * 增强的WebSocket服务
 * 支持多场站实时数据推送、事件管理和重连机制
 */
class WebSocketService {
  constructor() {
    this.socket = null
    this.backendBaseUrl = this.getBackendBaseUrl()
    this.isConnected = false
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 10
    this.eventListeners = new Map()
    this.farmSubscriptions = new Set()
    this.connectionPromise = null
  }

  /**
   * 获取后端基础URL
   */
  getBackendBaseUrl() {
    if (window.location.hostname !== 'localhost') {
      return `http://${window.location.hostname}:5000`
    }
    return 'http://localhost:5000'
  }

  /**
   * 初始化WebSocket连接
   */
  async connect() {
    if (this.isConnected && this.socket) {
      return this.socket
    }

    if (this.connectionPromise) {
      return this.connectionPromise
    }

    this.connectionPromise = new Promise((resolve, reject) => {
      try {
        const options = {
          reconnection: true,
          reconnectionAttempts: this.maxReconnectAttempts,
          reconnectionDelay: 1000,
          reconnectionDelayMax: 5000,
          timeout: 20000,
          transports: ['websocket', 'polling'],
          query: {
            farm_code: farmService.getCurrentFarm(),
            client_type: 'web',
            timestamp: Date.now()
          }
        }

        this.socket = io(this.backendBaseUrl, options)

        this.setupSocketListeners()

        this.socket.on('connect', () => {
          this.isConnected = true
          this.reconnectAttempts = 0
          console.log('WebSocket连接成功')
          this.emit('connection:connected', { farmCode: farmService.getCurrentFarm() })
          resolve(this.socket)
        })

        this.socket.on('connect_error', (error) => {
          console.error('WebSocket连接失败:', error)
          this.isConnected = false
          this.emit('connection:error', error)
          reject(error)
        })

      } catch (error) {
        this.connectionPromise = null
        reject(error)
      }
    })

    return this.connectionPromise
  }

  /**
   * 设置Socket事件监听器
   */
  setupSocketListeners() {
    // 连接状态监听
    this.socket.on('disconnect', (reason) => {
      this.isConnected = false
      console.log(`WebSocket断开连接: ${reason}`)
      this.emit('connection:disconnected', { reason })

      // 非主动断开时尝试重连
      if (reason !== 'io client disconnect') {
        this.handleReconnection()
      }
    })

    // 重连相关监听
    this.socket.on('reconnect', (attemptNumber) => {
      this.isConnected = true
      this.reconnectAttempts = 0
      console.log(`WebSocket重连成功，尝试次数: ${attemptNumber}`)
      this.emit('connection:reconnected', { attemptNumber })

      // 重新订阅场站数据
      this.resubscribeToFarms()
    })

    this.socket.on('reconnect_attempt', (attemptNumber) => {
      this.reconnectAttempts = attemptNumber
      console.log(`WebSocket重连尝试: ${attemptNumber}/${this.maxReconnectAttempts}`)
      this.emit('connection:reconnecting', { attemptNumber })
    })

    this.socket.on('reconnect_failed', () => {
      console.error('WebSocket重连失败')
      this.emit('connection:failed')
    })

    // 场站数据相关监听
    this.socket.on('farm:data', (data) => {
      this.handleFarmData(data)
    })

    this.socket.on('farm:alert', (data) => {
      this.handleFarmAlert(data)
    })

    this.socket.on('farm:status', (data) => {
      this.handleFarmStatus(data)
    })

    // 系统消息监听
    this.socket.on('system:message', (data) => {
      this.handleSystemMessage(data)
    })

    // 实时预测数据监听
    this.socket.on('prediction:update', (data) => {
      this.handlePredictionUpdate(data)
    })

    // 实时性能数据监听
    this.socket.on('performance:metrics', (data) => {
      this.handlePerformanceMetrics(data)
    })

    // 日志消息监听（兼容现有实现）
    this.socket.on('log', (data) => {
      this.handleLogMessage(data)
    })
  }

  /**
   * 处理重连逻辑
   */
  handleReconnection() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      console.log(`等待重连... (${this.reconnectAttempts + 1}/${this.maxReconnectAttempts})`)
    } else {
      console.error('达到最大重连次数，停止重连')
      this.emit('connection:max_attempts_reached')
    }
  }

  /**
   * 处理场站数据
   */
  handleFarmData(data) {
    // 验证数据是否属于当前订阅的场站
    if (data.farm_code && this.farmSubscriptions.has(data.farm_code)) {
      this.emit('farm:data:received', data)
    }
  }

  /**
   * 处理场站告警
   */
  handleFarmAlert(data) {
    if (data.farm_code && this.farmSubscriptions.has(data.farm_code)) {
      this.emit('farm:alert:received', data)
    }
  }

  /**
   * 处理场站状态
   */
  handleFarmStatus(data) {
    if (data.farm_code && this.farmSubscriptions.has(data.farm_code)) {
      this.emit('farm:status:received', data)
    }
  }

  /**
   * 处理系统消息
   */
  handleSystemMessage(data) {
    this.emit('system:message:received', data)
  }

  /**
   * 处理预测更新
   */
  handlePredictionUpdate(data) {
    if (data.farm_code && this.farmSubscriptions.has(data.farm_code)) {
      this.emit('prediction:update:received', data)
    }
  }

  /**
   * 处理性能指标
   */
  handlePerformanceMetrics(data) {
    this.emit('performance:metrics:received', data)
  }

  /**
   * 处理日志消息
   */
  handleLogMessage(data) {
    // 兼容现有的日志处理逻辑
    if (!data || !data.message) {
      console.error('收到无效的日志数据:', data)
      return
    }
    this.emit('log:received', data)
  }

  /**
   * 订阅场站数据
   */
  async subscribeToFarm(farmCode) {
    if (!this.isConnected) {
      await this.connect()
    }

    if (this.socket) {
      this.socket.emit('farm:subscribe', { farm_code: farmCode })
      this.farmSubscriptions.add(farmCode)
      console.log(`已订阅场站数据: ${farmCode}`)
    }
  }

  /**
   * 取消订阅场站数据
   */
  unsubscribeFromFarm(farmCode) {
    if (this.socket && this.isConnected) {
      this.socket.emit('farm:unsubscribe', { farm_code: farmCode })
      this.farmSubscriptions.delete(farmCode)
      console.log(`已取消订阅场站数据: ${farmCode}`)
    }
  }

  /**
   * 重新订阅场站数据
   */
  resubscribeToFarms() {
    if (this.farmSubscriptions.size > 0) {
      console.log('重新订阅场站数据...')
      this.farmSubscriptions.forEach(farmCode => {
        this.subscribeToFarm(farmCode)
      })
    }
  }

  /**
   * 订阅当前场站数据
   */
  async subscribeToCurrentFarm() {
    const currentFarm = farmService.getCurrentFarm()
    await this.subscribeToFarm(currentFarm)
  }

  /**
   * 切换场站订阅
   */
  async switchFarmSubscription(oldFarmCode, newFarmCode) {
    try {
      // 取消订阅旧场站
      if (oldFarmCode && this.farmSubscriptions.has(oldFarmCode)) {
        this.unsubscribeFromFarm(oldFarmCode)
      }

      // 订阅新场站
      await this.subscribeToFarm(newFarmCode)
      console.log(`场站订阅已切换: ${oldFarmCode} -> ${newFarmCode}`)
    } catch (error) {
      console.error('切换场站订阅失败:', error)
    }
  }

  /**
   * 发送消息到服务器
   */
  send(event, data) {
    if (this.socket && this.isConnected) {
      this.socket.emit(event, {
        ...data,
        farm_code: farmService.getCurrentFarm(),
        timestamp: Date.now()
      })
    } else {
      console.warn('WebSocket未连接，无法发送消息')
    }
  }

  /**
   * 添加事件监听器
   */
  on(event, callback) {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, new Set())
    }
    this.eventListeners.get(event).add(callback)
  }

  /**
   * 移除事件监听器
   */
  off(event, callback) {
    if (this.eventListeners.has(event)) {
      this.eventListeners.get(event).delete(callback)
    }
  }

  /**
   * 触发事件
   */
  emit(event, data) {
    if (this.eventListeners.has(event)) {
      this.eventListeners.get(event).forEach(callback => {
        try {
          callback(data)
        } catch (error) {
          console.error(`事件处理失败 [${event}]:`, error)
        }
      })
    }
  }

  /**
   * 获取连接状态
   */
  getConnectionStatus() {
    return {
      isConnected: this.isConnected,
      reconnectAttempts: this.reconnectAttempts,
      maxReconnectAttempts: this.maxReconnectAttempts,
      subscribedFarms: Array.from(this.farmSubscriptions)
    }
  }

  /**
   * 断开连接
   */
  disconnect() {
    if (this.socket) {
      this.socket.disconnect()
      this.isConnected = false
      this.connectionPromise = null
      this.farmSubscriptions.clear()
      console.log('WebSocket连接已断开')
    }
  }

  /**
   * 销毁服务
   */
  destroy() {
    this.disconnect()
    this.eventListeners.clear()
  }
}

// 创建单例实例
const websocketService = new WebSocketService()

// 导出单例
export default websocketService

// 导出便捷的Hook函数
export function useRealtimeData(options = {}) {
  const {
    autoConnect = true,
    autoSubscribe = true,
    onDataReceived = null,
    onAlertReceived = null,
    onStatusReceived = null
  } = options

  const connectionStatus = ref(websocketService.getConnectionStatus())
  const farmData = ref(null)
  const alerts = ref([])
  const status = ref({})

  // 更新连接状态
  const updateConnectionStatus = () => {
    connectionStatus.value = websocketService.getConnectionStatus()
  }

  // 处理数据接收
  const handleDataReceived = (data) => {
    farmData.value = data
    if (onDataReceived) {
      onDataReceived(data)
    }
  }

  // 处理告警接收
  const handleAlertReceived = (alert) => {
    alerts.value.push(alert)
    if (onAlertReceived) {
      onAlertReceived(alert)
    }
  }

  // 处理状态接收
  const handleStatusReceived = (statusData) => {
    status.value = { ...status.value, ...statusData }
    if (onStatusReceived) {
      onStatusReceived(statusData)
    }
  }

  // 处理场站变化
  const handleFarmChange = () => {
    if (connectionStatus.value.isConnected) {
      websocketService.subscribeToCurrentFarm()
    }
  }

  // 生命周期钩子
  onMounted(async () => {
    // 添加事件监听器
    websocketService.on('connection:connected', updateConnectionStatus)
    websocketService.on('connection:disconnected', updateConnectionStatus)
    websocketService.on('connection:reconnected', updateConnectionStatus)
    websocketService.on('farm:data:received', handleDataReceived)
    websocketService.on('farm:alert:received', handleAlertReceived)
    websocketService.on('farm:status:received', handleStatusReceived)

    // 添加场站变化监听器
    farmService.addListener(handleFarmChange)

    // 自动连接
    if (autoConnect) {
      await websocketService.connect()
    }

    // 自动订阅
    if (autoSubscribe && autoConnect) {
      await websocketService.subscribeToCurrentFarm()
    }
  })

  onUnmounted(() => {
    // 移除事件监听器
    websocketService.off('connection:connected', updateConnectionStatus)
    websocketService.off('connection:disconnected', updateConnectionStatus)
    websocketService.off('connection:reconnected', updateConnectionStatus)
    websocketService.off('farm:data:received', handleDataReceived)
    websocketService.off('farm:alert:received', handleAlertReceived)
    websocketService.off('farm:status:received', handleStatusReceived)

    // 移除场站变化监听器
    farmService.removeListener(handleFarmChange)
  })

  return {
    connectionStatus,
    farmData,
    alerts,
    status,
    subscribeToFarm: websocketService.subscribeToFarm.bind(websocketService),
    unsubscribeFromFarm: websocketService.unsubscribeFromFarm.bind(websocketService),
    send: websocketService.send.bind(websocketService),
    connect: websocketService.connect.bind(websocketService),
    disconnect: websocketService.disconnect.bind(websocketService)
  }
}
