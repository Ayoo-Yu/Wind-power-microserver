<template>
  <div class="system-maintenance">
    <!-- 页面标题 -->
    <div class="page-header">
      <h2 class="page-title">系统维护</h2>
      <p class="page-description">查看系统硬件配置、软件环境和运行参数信息</p>
    </div>

    <!-- 系统信息卡片 -->
    <div class="system-cards">
      <!-- 硬件系统信息 -->
      <el-card class="info-card hardware-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <el-icon class="card-icon"><Monitor /></el-icon>
            <span class="card-title">硬件系统</span>
            <el-button 
              type="primary" 
              size="small" 
              @click="refreshHardwareInfo"
              :loading="loadingHardware"
            >
              刷新
            </el-button>
          </div>
        </template>
        
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">CPU</span>
            <span class="info-value">{{ hardwareInfo.cpu }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">内存</span>
            <span class="info-value">{{ hardwareInfo.memory }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">存储</span>
            <span class="info-value">{{ hardwareInfo.storage }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">网络</span>
            <span class="info-value">{{ hardwareInfo.network }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">GPU</span>
            <span class="info-value">{{ hardwareInfo.gpu }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">系统架构</span>
            <span class="info-value">{{ hardwareInfo.architecture }}</span>
          </div>
        </div>
      </el-card>

      <!-- 软件系统信息 -->
      <el-card class="info-card software-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <el-icon class="card-icon"><Platform /></el-icon>
            <span class="card-title">软件系统</span>
            <el-button 
              type="primary" 
              size="small" 
              @click="refreshSoftwareInfo"
              :loading="loadingSoftware"
            >
              刷新
            </el-button>
          </div>
        </template>
        
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">操作系统</span>
            <span class="info-value">{{ softwareInfo.os }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">Python版本</span>
            <span class="info-value">{{ softwareInfo.python }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">Node.js版本</span>
            <span class="info-value">{{ softwareInfo.nodejs }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">数据库</span>
            <span class="info-value">{{ softwareInfo.database }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">Web服务器</span>
            <span class="info-value">{{ softwareInfo.webserver }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">系统版本</span>
            <span class="info-value">{{ softwareInfo.version }}</span>
          </div>
        </div>
      </el-card>

      <!-- 运行参数信息 -->
      <el-card class="info-card runtime-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <el-icon class="card-icon"><Setting /></el-icon>
            <span class="card-title">运行参数</span>
            <el-button 
              type="primary" 
              size="small" 
              @click="refreshRuntimeInfo"
              :loading="loadingRuntime"
            >
              刷新
            </el-button>
          </div>
        </template>
        
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">系统运行时间</span>
            <span class="info-value">{{ runtimeInfo.uptime }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">CPU使用率</span>
            <span class="info-value">
              <el-progress 
                :percentage="runtimeInfo.cpuUsage" 
                :color="getProgressColor(runtimeInfo.cpuUsage)"
                :show-text="true"
                :format="(percentage) => `${percentage}%`"
              />
            </span>
          </div>
          <div class="info-item">
            <span class="info-label">内存使用率</span>
            <span class="info-value">
              <el-progress 
                :percentage="runtimeInfo.memoryUsage" 
                :color="getProgressColor(runtimeInfo.memoryUsage)"
                :show-text="true"
                :format="(percentage) => `${percentage}%`"
              />
            </span>
          </div>
          <div class="info-item">
            <span class="info-label">磁盘使用率</span>
            <span class="info-value">
              <el-progress 
                :percentage="runtimeInfo.diskUsage" 
                :color="getProgressColor(runtimeInfo.diskUsage)"
                :show-text="true"
                :format="(percentage) => `${percentage}%`"
              />
            </span>
          </div>
          <div class="info-item">
            <span class="info-label">活跃连接数</span>
            <span class="info-value">{{ runtimeInfo.connections }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">最后更新时间</span>
            <span class="info-value">{{ runtimeInfo.lastUpdate }}</span>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 系统日志预览 -->
    <el-card class="log-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <el-icon class="card-icon"><Document /></el-icon>
          <span class="card-title">系统日志</span>
          <div class="log-controls">
            <el-select v-model="selectedLogLevel" placeholder="日志级别" size="small" style="width: 120px; margin-right: 10px;">
              <el-option label="全部" value="all" />
              <el-option label="错误" value="error" />
              <el-option label="警告" value="warning" />
              <el-option label="信息" value="info" />
            </el-select>
            <el-button 
              type="primary" 
              size="small" 
              @click="refreshLogs"
              :loading="loadingLogs"
            >
              刷新日志
            </el-button>
          </div>
        </div>
      </template>
      
      <div class="log-container">
        <div v-if="logs.length === 0" class="no-logs">
          暂无日志信息
        </div>
        <div v-else class="log-list">
          <div 
            v-for="log in filteredLogs" 
            :key="log.id" 
            :class="['log-item', `log-${log.level}`]"
          >
            <span class="log-time">{{ log.timestamp }}</span>
            <span class="log-level">{{ log.level.toUpperCase() }}</span>
            <span class="log-message">{{ log.message }}</span>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getSystemHardware,
  getSystemSoftware,
  getSystemRuntime,
  getSystemLogs
} from '../api/systemApi'
import {
  Monitor,
  Platform,
  Setting,
  Document
} from '@element-plus/icons-vue'

export default {
  name: 'SystemMaintenance',
  components: {
    Monitor,
    Platform,
    Setting,
    Document
  },
  setup() {
    // 加载状态
    const loadingHardware = ref(false)
    const loadingSoftware = ref(false)
    const loadingRuntime = ref(false)
    const loadingLogs = ref(false)

    // 硬件信息
    const hardwareInfo = ref({
      cpu: '获取中...',
      memory: '获取中...',
      storage: '获取中...',
      network: '获取中...',
      gpu: '获取中...',
      architecture: '获取中...'
    })

    // 软件信息
    const softwareInfo = ref({
      os: '获取中...',
      python: '获取中...',
      nodejs: '获取中...',
      database: '获取中...',
      webserver: '获取中...',
      version: '获取中...'
    })

    // 运行参数
    const runtimeInfo = ref({
      uptime: '获取中...',
      cpuUsage: 0,
      memoryUsage: 0,
      diskUsage: 0,
      connections: 0,
      lastUpdate: '获取中...'
    })

    // 日志相关
    const selectedLogLevel = ref('all')
    const logs = ref([])

    // 过滤后的日志
    const filteredLogs = computed(() => {
      if (selectedLogLevel.value === 'all') {
        return logs.value
      }
      return logs.value.filter(log => log.level === selectedLogLevel.value)
    })

    // 获取进度条颜色
    const getProgressColor = (percentage) => {
      if (percentage < 50) return '#67c23a'
      if (percentage < 80) return '#e6a23c'
      return '#f56c6c'
    }

    // 刷新硬件信息
    const refreshHardwareInfo = async () => {
      loadingHardware.value = true
      try {
        const response = await getSystemHardware()
        hardwareInfo.value = response.data
        ElMessage.success('硬件信息已更新')
      } catch (error) {
        console.error('获取硬件信息失败:', error)
        ElMessage.error('获取硬件信息失败')
      } finally {
        loadingHardware.value = false
      }
    }

    // 刷新软件信息
    const refreshSoftwareInfo = async () => {
      loadingSoftware.value = true
      try {
        const response = await getSystemSoftware()
        softwareInfo.value = response.data
        ElMessage.success('软件信息已更新')
      } catch (error) {
        console.error('获取软件信息失败:', error)
        ElMessage.error('获取软件信息失败')
      } finally {
        loadingSoftware.value = false
      }
    }

    // 刷新运行参数
    const refreshRuntimeInfo = async () => {
      loadingRuntime.value = true
      try {
        const response = await getSystemRuntime()
        runtimeInfo.value = response.data
        ElMessage.success('运行参数已更新')
      } catch (error) {
        console.error('获取运行参数失败:', error)
        ElMessage.error('获取运行参数失败')
      } finally {
        loadingRuntime.value = false
      }
    }

    // 刷新日志
    const refreshLogs = async () => {
      loadingLogs.value = true
      try {
        const response = await getSystemLogs()
        logs.value = response.data
        ElMessage.success('日志已更新')
      } catch (error) {
        console.error('获取日志失败:', error)
        ElMessage.error('获取日志失败')
      } finally {
        loadingLogs.value = false
      }
    }

    // 初始化所有数据
    const initializeData = async () => {
      await Promise.all([
        refreshHardwareInfo(),
        refreshSoftwareInfo(),
        refreshRuntimeInfo(),
        refreshLogs()
      ])
    }

    // 组件挂载时初始化
    onMounted(() => {
      initializeData()
    })

    return {
      loadingHardware,
      loadingSoftware,
      loadingRuntime,
      loadingLogs,
      hardwareInfo,
      softwareInfo,
      runtimeInfo,
      selectedLogLevel,
      logs,
      filteredLogs,
      getProgressColor,
      refreshHardwareInfo,
      refreshSoftwareInfo,
      refreshRuntimeInfo,
      refreshLogs
    }
  }
}
</script>

<style scoped>
.system-maintenance {
  padding: 24px;
  background: transparent;
  min-height: 100vh;
  position: relative;
}

.page-header {
  margin-bottom: 32px;
  text-align: center;
  position: relative;
  z-index: 1;
}

.page-title {
  font-size: 32px;
  font-weight: 700;
  color: #ffffff;
  margin: 0 0 12px 0;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  letter-spacing: 1px;
}

.page-description {
  font-size: 18px;
  color: rgba(255, 255, 255, 0.9);
  margin: 0;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
}

.system-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
  gap: 24px;
  margin-bottom: 24px;
  position: relative;
  z-index: 1;
}

.info-card {
  background: rgba(7, 24, 39, 0.58);
  backdrop-filter: blur(15px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 20px;
  transition: all 0.3s ease;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
}

.info-card:hover {
  transform: translateY(-6px);
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.2);
  background: rgba(7, 24, 39, 0.58);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  color: var(--text-primary);
}

.card-icon {
  font-size: 20px;
  margin-right: 8px;
}

.card-title {
  flex: 1;
  font-size: 18px;
}

.hardware-card .card-icon {
  color: #409eff;
}

.software-card .card-icon {
  color: #67c23a;
}

.runtime-card .card-icon {
  color: #e6a23c;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  padding: 16px;
  background: rgba(18, 215, 255, 0.06);
  border-radius: 12px;
  transition: background 0.3s ease;
}

.info-item:hover {
  background: rgba(18, 215, 255, 0.08);
}

.info-label {
  font-size: 14px;
  color: var(--text-muted);
  margin-bottom: 8px;
  font-weight: 500;
}

.info-value {
  font-size: 16px;
  color: var(--text-primary);
  font-weight: 600;
  line-height: 1.4;
}

.log-card {
  background: rgba(7, 24, 39, 0.58);
  backdrop-filter: blur(15px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 20px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
  position: relative;
  z-index: 1;
}

.log-controls {
  display: flex;
  align-items: center;
}

.log-container {
  max-height: 400px;
  overflow-y: auto;
}

.no-logs {
  text-align: center;
  color: var(--text-muted);
  font-size: 16px;
  padding: 40px;
}

.log-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.log-item {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.4;
  transition: background 0.3s ease;
}

.log-item:hover {
  background: rgba(18, 215, 255, 0.08);
}

.log-time {
  flex-shrink: 0;
  width: 140px;
  color: var(--text-muted);
  font-family: 'Courier New', monospace;
}

.log-level {
  flex-shrink: 0;
  width: 60px;
  font-weight: 600;
  font-family: 'Courier New', monospace;
}

.log-message {
  flex: 1;
  color: var(--text-primary);
  margin-left: 16px;
}

.log-info {
  background: rgba(64, 158, 255, 0.1);
}

.log-info .log-level {
  color: #409eff;
}

.log-warning {
  background: rgba(230, 162, 60, 0.1);
}

.log-warning .log-level {
  color: #e6a23c;
}

.log-error {
  background: rgba(245, 108, 108, 0.1);
}

.log-error .log-level {
  color: #f56c6c;
}

/* 进度条样式调整 */
:deep(.el-progress-bar__outer) {
  background-color: rgba(0, 0, 0, 0.1);
}

/* 背景动画 */
@keyframes gradient {
  0% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0% 50%;
  }
}

/* 为.system-maintenance添加伪元素背景 */
.system-maintenance::before {
  content: '';
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(-45deg, #ee7752, #e73c7e, #23a6d5, #23d5ab);
  background-size: 400% 400%;
  animation: gradient 15s ease infinite;
  z-index: -1;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .system-cards {
    grid-template-columns: 1fr;
  }
  
  .info-grid {
    grid-template-columns: 1fr;
  }
  
  .log-controls {
    flex-direction: column;
    gap: 8px;
    align-items: stretch;
  }
  
  .log-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
  
  .log-time,
  .log-level {
    width: auto;
  }
  
  .log-message {
    margin-left: 0;
  }
}
</style> 
